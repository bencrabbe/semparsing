#! /usr/bin/env python

"""
This module includes functions for calculating the pagerank for items of Wikidata via
a directed graph and for building a lexicon as a dictionnary.

(!) Time consuming and heavy ops due to large amounts of data.
Uses pytables (tables) as backend.    
"""

import gzip,bz2,json,sys,re
import urllib.request
from datetime import datetime
from tables import *
#from lexer import DefaultLexer
from ast import literal_eval


class WikidataEntity(IsDescription):

	ent_idx     = StringCol(16)     # the Qxxx string identifier of the entity
	qlabels     = StringCol(4096)   # the label of the entity and its aliases 
	nclaims     = Int64Col()        # the number of claims for the entity
	nlanguages  = Int64Col()        # the number of languages for the entity
	nsitelinks  = Int64Col()        # the number of sitelinks for the entity
	is_instance = BoolCol()         # states if entity isa P31 
	is_subclass = BoolCol()         # states if entity ako P279
	neg_page_rank   = Float64Col()  # provides the negative page rank of an entity (! set to 0 for properties)
	#wikipedia_url= StringCol(1028) # the url of the wikipedia page

	# here some attributes to store other information of the entity of Wikidata
	bridging    = StringCol(4096)
	#graph       = StringCol(30000)
	#nodes       = StringCol(4096)
	

class Graph(IsDescription):
	Q1 = StringCol(16)
	P1 = StringCol(16)
	P2 = StringCol(16)
	

def create_wikidata_subsetfile(dumpfile):
	 """
	 Creates the HDF5 file from the dumpfile name
	 """
	 h5filename    = '.'.join(dumpfile.split('.')[:-1]+['h5'])
	 h5file        = open_file(h5filename, mode="w", title="Wikidata subset")
	 egroup        = h5file.create_group("/", 'dbgroup', 'Entities and properties stats')
	 etable        = h5file.create_table(egroup, 'entities', WikidataEntity , "Entities stats")
	 h5file.close()
	 return h5filename

def extract_entities(dumpfile,h5filename,graphfilename,lang='fr'):
	"""
	Reads entities from a json.gz wikidata dump and filters out irrelevant entities.
	Stores the result in an HDF5 file

	That is an heavy operation (takes several hours).

	Args:
	   dumpfile   (string): a gzipped wikidata json filename
	   h5filename (string): name of the HDF5 file name
	   graphfilename (string) : 
	Kwargs:
	   lang     (string): language code of the language to extract
	Returns:
		a string, the name of the generated hdf5 table
	See also:  
		https://www.mediawiki.org/wiki/Wikibase/DataModel/JSON
	"""
	
	igzstream     = bz2.open(dumpfile)
	h5filename    = '.'.join(dumpfile.split('.')[:-1]+['h5'])
	h5file        = open_file(h5filename, mode="a")
	etable        = h5file.root.dbgroup.entities
	graphfi       = open(graphfilename,"w")
	
	def is_nlp_relevant(row):
		if row['ent_idx'][0] == "Q":
			return row['nlanguages'] > 0 and row['nsitelinks'] > 0 and row['nclaims'] > 0 and (row['is_instance'] or row['is_subclass'])
		else:
			return row['nlanguages'] > 0 and row['nclaims'] > 0 and (row['is_instance'] or row['is_subclass'])
	
	def get_graph(entity):
		graph = []
		for claim in entity['claims'].keys():
			for mainsnak in entity['claims'][claim]:
				if "datavalue" in mainsnak["mainsnak"]: 
					if "value" in mainsnak["mainsnak"]["datavalue"]:
						if "id" in mainsnak["mainsnak"]["datavalue"]["value"] and type(mainsnak["mainsnak"]["datavalue"]["value"]) is dict:
							Q2 = mainsnak["mainsnak"]["datavalue"]["value"]["id"]

							if "qualifiers" in mainsnak:
								for qualifiers in mainsnak["qualifiers"]:
									if "datavalue" in mainsnak["qualifiers"][qualifiers][0]:
										if "value" in mainsnak["qualifiers"][qualifiers][0]["datavalue"]:
											if "id" in mainsnak["qualifiers"][qualifiers][0]["datavalue"]["value"] and type(mainsnak["qualifiers"][qualifiers][0]["datavalue"]["value"]) is dict:
												Q3 = mainsnak["qualifiers"][qualifiers][0]["datavalue"]["value"]["id"]
												graph.append(str([entity['id'],claim,Q2,qualifiers,Q3]))
											else:
												graph.append(str([entity['id'],claim,Q2]))
							else:
								graph.append(str([entity['id'],claim,Q2]))
						
						elif "qualifiers" in mainsnak:
							for qualifiers in mainsnak["qualifiers"]:
								if "datavalue" in mainsnak["qualifiers"][qualifiers][0]:
									if "value" in mainsnak["qualifiers"][qualifiers][0]["datavalue"]:
										if "id" in mainsnak["qualifiers"][qualifiers][0]["datavalue"]["value"] and type(mainsnak["qualifiers"][qualifiers][0]["datavalue"]["value"]) is dict:
											Q2 = mainsnak["qualifiers"][qualifiers][0]["datavalue"]["value"]["id"]
											graph.append(str([entity['id'],claim,qualifiers,Q2]))

		return graph

	tptr   = etable.row
	eadd,eread = 0,0
	maxlblL = 0
	entity = igzstream.readline() #skip init 
	entity = igzstream.readline()
	while entity:
		entity = entity.decode('utf-8')[:-2]
		if entity and entity[0] == '{':
			try :
				entity = json.loads(entity)
				if 'en' in entity['labels']:
					qlabel  = [ entity['labels']['en']['value'] ]
					if lang in entity['labels']:
						qlabel.append( entity['labels'][lang]['value'] )
					if lang in entity['aliases']:
						qlabel.extend( [elt['value'] for elt in entity['aliases'][lang]] )
					qlabel = list(set(qlabel))
					enc_label = ';'.join(qlabel).encode('utf-8') #use foo.decode('utf-8') when getting values out of the table
					maxlblL = max(maxlblL, len(enc_label))
					ent_id  = entity['id']                #Pxxx or Qxxx
					tptr['qlabels']     = enc_label
					tptr['ent_idx']     = ent_id            
					tptr['nclaims']     = len(entity['claims'].keys())    if 'claims'    in entity else 0
					tptr['nlanguages']  = len(entity['labels'].keys())    if 'labels'    in entity else 0
					tptr['nsitelinks']  = len(entity['sitelinks'].keys()) if 'sitelinks' in entity else 0
					tptr['is_instance'] = 'P31'  in entity['claims']
					tptr['is_subclass'] = 'P279' in entity['claims']
					tptr['bridging']    = ';;'.join(list(entity['claims'].keys())).encode('utf-8')
					
					if is_nlp_relevant(tptr):
						tptr.append()
						graph = get_graph(entity)
						if graph:
							graph = '\t'.join(graph)
							graphfi.write(graph+"\n")
						eadd += 1
						if eadd % 10000 == 0:
							print ('Added', eadd, 'entities','Read',eread,'entities','Max label length (in bytes)',maxlblL,flush=True)
					eread += 1
			except Exception as e:
				print('@@@',type(e),e)
							
		entity = igzstream.readline()
	igzstream.close()
	etable.flush()

	h5file.close()
	print('Reading done...')



if __name__ == '__main__':
	dumpname = "wikidata-20180101-all.json.bz2"
	h5filename = create_wikidata_subsetfile(dumpname)
	#h5filename = "wikidata-20180101-all.json.h5"
	graphfilename = "graph.txt"
	#extract_entities(dumpname, h5filename, graphfilename, lang="fr")

	"""
	h5file        = open_file("wikidata-2018-01-01.json.h5", mode="a") 
	etable        = h5file.root.dbgroup.entities 
	for entity in etable:
		labels = entity['qlabels'].decode('utf-8').split(';')
		print(labels)
		print()
	print("done")
	h5file.close()
	"""
	"""
	fi = open("graph.txt").read().split("\n")
	for line in fi:
		if line:
			line = line.split("\t")
			for elt in line:
				print(literal_eval(elt)[0])
			input()
			"""






