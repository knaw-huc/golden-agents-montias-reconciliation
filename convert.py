"""
Convert the Getty's Dutch Archival Descriptions and Contents to a basic RDF format.
"""

import os
import csv
import string

import re
from datetime import datetime

from rdflib import Dataset, Graph, Namespace, URIRef, Literal, BNode
from rdflib import RDF, RDFS, XSD

ga = Namespace("http://goldenagents.org/uva/SAA/datasets/")
saa = Namespace("http://goldenagents.org/uva/SAA/ontology/")

saaPerson = Namespace("http://goldenagents.org/uva/SAA/Person/")
saaInventory = Namespace("http://goldenagents.org/uva/SAA/Inventory/")
saaItem = Namespace("http://goldenagents.org/uva/SAA/Inventory/Item/")

tgn = Namespace("http://vocab.getty.edu/tgn/")

ARCHIVE_DESCRIPTIONS = 'data/dutch_archival_descriptions_utf8.csv'
ARCHIVE_ITEMS = 'data/dutch_archival_contents_utf8.csv'

############################################################
# Mapping to the Getty Thesaurus of Geographic Names (TGN) #
############################################################

COUNTRIES = {
    'Netherlands': tgn.term('7016845'),
    'Belgium': tgn.term('1000063'),
    'Germany': tgn.term('7000084')
}

CITIES = {
    'Alkmaar': tgn.term('7007057'),
    'Amsterdam': tgn.term('7006952'),
    'Antwerp': tgn.term('7007856'),
    'Dordrecht': tgn.term('7006798'),
    'Haarlem': tgn.term('7007048'),
    'Hamburg': tgn.term('7005289'),
    'Hoorn': tgn.term('7007056'),
    'Leiden': tgn.term('7006809'),
    'Hague, The': tgn.term('7006810'),
    'Utrecht': tgn.term('7006926'),
    'Wijk bij Duurstede': tgn.term('7017400')
}


def main(dataset):

    g = dataset.graph(identifier=ga.term('Dutch_Archival_Inventories'))

    # Add labels for the countries and cities
    for label, value in {**COUNTRIES, **CITIES}.items():
        g.add((value, RDFS.label, Literal(label, lang='en-US')))

    # Add descriptions
    with open(ARCHIVE_DESCRIPTIONS, encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for r in reader:
            g = description2rdf(r, g=g)

    # Add items
    with open(ARCHIVE_ITEMS, encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for r in reader:
            g = items2rdf(r, g=g)

    return dataset


def description2rdf(record, g):
    """Convert the list of Archival Descriptions to RDF.
    
    Args:
        record (dict): row in the descriptions csv
        g (rdflib.Graph): named graph
    
    Returns:
        rdflib.Graph: named graph
    """

    inventory = saaInventory.term(record['pi_record_no'])

    g.add((inventory, RDF.type, saa.Inventory))
    g.add((inventory, saa.identifier, Literal(record['pi_record_no'])))

    country = COUNTRIES.get(record['country_auth'], None)
    city = CITIES.get(record['city_auth'], None)

    comment = record['introduction']
    if comment != "":
        g.add((inventory, RDFS.comment, Literal(comment, lang='nl')))

    if country is not None:
        g.add((inventory, saa.country, country))
    if city is not None:
        g.add((inventory, saa.city, city), )

    g.add((inventory, saa.documentType,
           Literal(record['document_type'], lang='en-US')))

    owners, g = getOwners(record, g=g, inventory=inventory)

    for owner in owners:
        g.add((inventory, saa.owners, owner))

    beneficiaries, g = getBeneficiaries(record, g=g, inventory=inventory)

    for beneficiary in beneficiaries:
        g.add((inventory, saa.beneficiaries, beneficiary))

    appraisers, g = getAppraisers(record, g=g, inventory=inventory)

    for beneficiary in appraisers:
        g.add((inventory, saa.appraisers, beneficiary))

    try:
        beginDate = datetime(int(record['begin_date_year']),
                             int(record['begin_date_month']),
                             int(record['begin_date_day']))
        g.add((inventory, saa.beginDate,
               Literal(beginDate.strftime('%Y-%m-%d'), datatype=XSD.date)))
    except:
        beginDate = None

    try:
        endDate = datetime(int(record['end_date_year']),
                           int(record['end_date_month']),
                           int(record['end_date_day']))
        g.add((inventory, saa.endDate,
               Literal(endDate.strftime('%Y-%m-%d'), datatype=XSD.date)))
    except:
        endDate = None

    # Pick one date as registrationDate.
    if all([beginDate, endDate]):
        date = beginDate
    elif beginDate is None:
        date = endDate
    elif endDate is None:
        date = beginDate
    else:
        date = None

    if date is not None:
        g.add((inventory, saa.registrationDate,
               Literal(date.strftime('%Y-%m-%d'), datatype=XSD.date)))

    archive, g = getArchive(record, g)
    if archive is not None:
        g.add((inventory, saa.archive, archive))

    if record['archive_doc_no'] != "":
        g.add((inventory, saa.archiveDocumentReference,
               Literal(record['archive_doc_no'])))

        # For matching with the Notarial Archives from the SAA / Golden Agents
        if 'Amsterdam' in record['archive_loc']:
            inventoryNumber = re.findall(r'(?:(?:NAA)|(?:GAA NA)) ([^ \,)]*)',
                                         record['archive_doc_no'])
            if inventoryNumber != []:
                inventoryNumber = inventoryNumber[0].upper()

                book = BNode(f"saaInventory{inventoryNumber}")
                g.add((book, saa.inventoryNumber, Literal(inventoryNumber)))
                if archive is not None:
                    g.add((book, saa.heldBy, archive))

                g.add((inventory, saa.documentedIn, book))

    return g


def getOwners(record, g, inventory):

    owners = []

    # TODO ?
    # Is it usefull to parse this stuff at this point? The Getty is doing
    # a standardization of the person names to the Getty ULAN, so eventually
    # this information will be incorporated over there. It is, however, usefull
    # for Golden Agents in the disambiguation/dedupliation of entities in the
    # SAA-dataset...

    residence = record.get('owner_residence', None)
    for n in range(1, 6):
        field_name = f"owner_name_{n}"
        field_name_mod = f"owner_name_mod_{n}"
        field_lifespan = f"owner_name_life_{n}"
        field_occupation = f"owner_name_occu_{n}"

        name = record[field_name]

        if name != "":
            owner = saaPerson.term(
                f"{record['pi_record_no']}owner{str(n).zfill(2)}")
            g.add((owner, RDF.type, saa.Person))
            g.add((owner, RDFS.label, Literal(name)))

            # backref
            g.add((owner, saa.isInRecord, inventory))

            owners.append(owner)

    return owners, g


def getBeneficiaries(record, g, inventory):

    beneficiaries = []

    for n in range(1, 13):

        field_name = f"benef_name_{n}"

        name = record[field_name]

        if name != "":
            beneficiary = saaPerson.term(
                f"{record['pi_record_no']}beneficiary{str(n).zfill(2)}")
            g.add((beneficiary, RDF.type, saa.Person))
            g.add((beneficiary, RDFS.label, Literal(name)))

            # backref
            g.add((beneficiary, saa.isInRecord, inventory))

            beneficiaries.append(beneficiary)

    return beneficiaries, g


def getAppraisers(record, g, inventory):

    appraisers = []

    for n in range(1, 15):

        field_name = f"appraiser_{n}"

        name = record[field_name]

        if name != "":
            appraiser = saaPerson.term(
                f"{record['pi_record_no']}appraiser{str(n).zfill(2)}")
            g.add((appraiser, RDF.type, saa.Person))
            g.add((appraiser, RDFS.label, Literal(name)))

            # backref
            g.add((appraiser, saa.isInRecord, inventory))

            appraisers.append(appraiser)

    return appraisers, g


def getArchive(record, g):
    """
    archive_name	archive_loc	    archive_doc_no   
    """

    if record['archive_name'] != "":
        uniquename = "".join(i for i in record['archive_name'] +
                             record['archive_loc']
                             if i in string.ascii_letters)
        archive = BNode(uniquename)

        g.add((archive, RDF.type, saa.Archive))
        g.add((archive, RDFS.label, Literal(record['archive_name'])))

        if record['archive_loc'] != "":
            g.add((archive, saa.location, Literal(record['archive_loc'])))

        return archive, g
    else:
        return None, g


def items2rdf(record, g):
    """Convert the list of Archival Items to RDF
    
    Args:
        record (dict): row in the items csv
        g (rdflib.Graph): named graph
    
    Returns:
        rdflib.Graph: named graph
    """
    inventory = saaInventory.term(record['pi_inventory_no'])
    item = saaItem.term(
        f"{record['pi_inventory_no']}_{record['assigned_item_no'].zfill(4)}")

    g.add((inventory, saa.content, item))
    g.add((item, saa.isInRecord, inventory))

    # Info on the item
    g.add((item, RDF.type, saa.Item))
    g.add((item, saa.term('index'), Literal(record['assigned_item_no'])))

    if record['persistent_uid'] != "":
        g.add((item, saa.identifier, Literal(record['persistent_uid'])))

    g.add((item, RDFS.label, Literal(record['title'], lang='nl')))
    g.add((item, saa.transcription, Literal(record['entry'], lang='nl')))

    if record['room'] != "":
        g.add((item, saa.room, Literal(record['room'], lang='nl')))

    if record['valuation_amount'] != "":
        g.add((item, saa.valuation, Literal(record['valuation_amount'])))

    return g


if __name__ == "__main__":

    ds = Dataset()
    ds.bind('ga', ga)
    ds.bind('saa', saa)

    ds = main(dataset=ds)
    ds.serialize('Dutch_Archival_Descriptions.trig', format='trig')