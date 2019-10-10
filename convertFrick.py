"""
Convert the Frick's Montias Dutch Archival Descriptions and Contents to a basic RDF format.

Example TriG:
    todo
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

ARCHIVE_DESCRIPTIONS = 'data/MontiasSets/InventoryExport.csv'
ARCHIVE_ITEMS = 'data/MontiasSets/Montias2ArtExport.csv'

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
    """Process the Frick/Montias Archival Descriptions and the Archival Contents. 
    
    Args:
        dataset (rdflib.Dataset): Dataset container to store named graphs
    
    Returns:
        rdflib.Dataset: A dataset (similar to rdflib.ConjunctiveGraph) with the
            converted Getty Dutch Archival Inventories data.
    """

    g = dataset.graph(identifier=ga.term('Dutch_Archival_Inventories_Frick'))

    # Add labels for the countries and cities
    for label, value in {**COUNTRIES, **CITIES}.items():
        g.add((value, RDFS.label, Literal(label, lang='en-US')))

    # Add descriptions
    with open(ARCHIVE_DESCRIPTIONS, encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        for r in reader:
            g = description2rdf(r, g=g)

    # # Add items
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

    # Add inventory as resource
    inventory = saaInventory.term(record['inventory_number'])

    g.add((inventory, RDF.type, saa.Inventory))
    g.add((inventory, saa.identifier, Literal(record['inventory_number'])))
    g.add((inventory, saa.montiasId, Literal(record['montias_id'])))

    country = COUNTRIES.get(record['country'], None)
    city = CITIES.get(record['city'], None)

    comment = record['introduction']
    if comment != "":
        g.add((inventory, RDFS.comment, Literal(comment, lang='nl')))
    commentary = record['commentary']
    if commentary != "":
        g.add((inventory, RDFS.comment, Literal(commentary, lang='en')))

    if country is not None:
        g.add((inventory, saa.country, country))
    if city is not None:
        g.add((inventory, saa.city, city), )

    g.add((inventory, saa.documentType, Literal(record['type'], lang='en-US')))

    # Add owners
    name = record['owner_name']
    if name != "":
        owner = saaPerson.term(f"{record['inventory_number']}owner01")
        g.add((owner, RDF.type, saa.Person))
        g.add((owner, RDFS.label, Literal(name)))

        g.add((inventory, saa.owners, owner))

        # backref
        g.add((owner, saa.isInRecord, inventory))

    # Add appraisers

    appraiser = record['appraiser']
    if appraiser != "":
        g.add((inventory, saa.appraisers, Literal(appraiser)))

    # Date

    date = record['date']
    date = date.replace('/', '-')  # and then it is iso-8601 valid!
    date = date.replace('c. ', '')

    g.add((inventory, saa.registrationDate, Literal(date, datatype=XSD.date)))

    # Add holding archive
    archive, g = getArchive(record, g)
    if archive is not None:
        g.add((inventory, saa.archive, archive))

    if record['call_number'] != "":
        g.add((inventory, saa.archiveDocumentReference,
               Literal(record['call_number'])))

        # For matching with the Notarial Archives from the SAA / Golden Agents
        archiveReference = record['call_number']

        if 'WK' in archiveReference:
            inventoryNumber = []
        elif 'DBK' in archiveReference:
            inventoryNumber = []
        elif 'boedel' in archiveReference:
            inventoryNumber = []
        else:
            inventoryNumber = re.findall(r"(?:NA)?[ ]?(\d{2,5}[ ]?[A-B]?)",
                                         archiveReference)

        if inventoryNumber != []:
            inventoryNumber = inventoryNumber[0].upper().replace(' ', '')

            book = BNode(f"saaInventory{inventoryNumber}")
            g.add((book, saa.inventoryNumber, Literal(inventoryNumber)))
            if archive is not None:
                g.add((book, saa.heldBy, archive))

            g.add((book, RDF.type, saa.InventoryBook))
            g.add((inventory, saa.documentedIn, book))

    return g


def getArchive(record, g):
    """Parse inventory holding archive and add to graph.
    
    Args:
        record (dict): Inventory information as dictionary (row from csv)
        g (rdflib.Graph): named graph
    
    Returns:
        tuple: Tuple of the archive (rdflib.URIRef) and the graph (rdflib.Graph).
    """

    if record['archive'] != "":
        uniquename = "".join(i for i in record['archive']
                             if i in string.ascii_letters)
        archive = BNode(uniquename)

        g.add((archive, RDF.type, saa.Archive))
        g.add((archive, RDFS.label, Literal(record['archive'])))

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
    inventory = saaInventory.term(record['inventory_number'])
    inventoryLot = re.sub(r'[\[\]`]', '', record['inventory_lot'])
    item = saaItem.term(inventoryLot)

    g.add((inventory, saa.content, item))
    g.add((item, saa.isInRecord, inventory))

    # Info on the item
    g.add((item, RDF.type, saa.Item))
    g.add((item, saa.term('index'), Literal(record['assigned_item_no'])))
    g.add((item, saa.workType, Literal(record['type'], lang='en')))

    # if record['persistent_uid'] != "":
    #     g.add((item, saa.identifier, Literal(record['persistent_uid'])))

    g.add((item, RDFS.label, Literal(record['title'], lang='nl')))
    g.add((item, saa.artist, Literal(record['artist_name'])))
    g.add((item, saa.transcription, Literal(record['entry'], lang='nl')))

    if record['room'] != "":
        g.add((item, saa.room, Literal(record['room'], lang='nl')))

    if record['value'] != "":
        g.add((item, saa.valuation, Literal(record['value'])))

    return g


if __name__ == "__main__":

    ds = Dataset()
    ds.bind('ga', ga)
    ds.bind('saa', saa)

    ds = main(dataset=ds)
    ds.serialize('Dutch_Archival_Descriptions_Frick.trig', format='trig')