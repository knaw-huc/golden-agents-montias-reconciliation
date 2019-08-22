"""
Match Getty/Frick records to an existing record from the Notarial Index

The query that was used is:

    ```sparql

    PREFIX saaOnt: <http://goldenagents.org/uva/SAA/ontology/>
    PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    SELECT ?dataset ?inventory ?inventoryNumber ?date ?owner_a ?documentType ?record ?actType ?owner_b WHERE {
    
    GRAPH ?g {
    ?inventory saaOnt:documentedIn/saaOnt:inventoryNumber ?inventoryNumber ;
                saaOnt:beginDate|saaOnt:endDate|saaOnt:registrationDate ?date ;
                saaOnt:owners/rdfs:label ?owner_a .
    
    OPTIONAL { ?inventory saaOnt:documentType ?documentType . }
    
    }
    
    ?record saaOnt:inventoryNumber ?inventoryNumber ;
            saaOnt:registrationDate ?date ;
            saaOnt:actType ?actType ;
            saaOnt:mentionsRegistered/rdfs:label ?owner_b .
    
    BIND( strafter( STR(?g), "_Inventories_" ) as ?dataset )
    
    } ORDER BY ?inventory

    ```

"""

from collections import defaultdict
import pandas as pd
from textacy.similarity import token_sort_ratio

MATCHESFILE = 'matchQueryResults.csv'


def main(filepath):

    linkset = defaultdict(set)

    df = pd.read_csv(filepath)

    for r in df.to_dict(orient='records'):

        dataset = r['dataset']

        a = r['owner_a']
        b = r['owner_b']

        p = token_sort_ratio(a, b)
        if p > .8:
            print(round(p, 2), a, b, sep='\t')

            if r['actType'] not in [
                    "Boedelinventaris", "Boedelscheiding", "Testament",
                    "Overig", "Huwelijkse voorwaarden", "Kwitantie"
            ]:
                continue

            linkset[r['inventory']].add(
                (r['dataset'], r['record'], r['actType']))

    return linkset


def buildLinkset(linkset, destination='linkset.ttl'):

    with open(destination, 'w') as outfile:
        outfile.write(
            '@prefix saa: <http://goldenagents.org/uva/SAA/ontology/> .\n')

        for inventory, match in linkset.items():
            for dataset, record, actType in match:
                outfile.write(f"<{record}> saa:inventory <{inventory}> .\n")
                outfile.write(f"<{inventory}> saa:isInRecord <{record}> .\n")


if __name__ == "__main__":
    linkset = main(MATCHESFILE)

    buildLinkset(linkset)
