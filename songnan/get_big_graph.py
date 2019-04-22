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



##########################################################################################
class WikidataEntity(IsDescription):

	ent_idx     = StringCol(16)     # the Qxxx string identifier of the entity
	qlabels     = StringCol(4096)   # the label of the entity and its aliases 
	# here some attributes to identify if the 
	nclaims     = Int64Col()        # the number of claims for the entity
	nlanguages  = Int64Col()        # the number of languages for the entity
	nsitelinks  = Int64Col()        # the number of sitelinks for the entity
	is_instance = BoolCol()         # states if entity isa P31 
	is_subclass = BoolCol()         # states if entity ako P279
	# here some attributes to store the information of the entity of Wikidata
	labels      = []
	aliases     = []
	relations   = []
	graph       = []
	neg_page_rank   = Float64Col()  # provides the negative page rank of an entity
	#wikipedia_url= StringCol(1028) # the url of the wikipedia page




########################################################################################## 
def extract_entities(dumpfile, savefile, lang='fr'):
	"""
	Reads entities from a json.gz wikidata dump and filters out irrelevant entities.
	Stores the result in an HDF5 file

	That is an heavy operation (takes several hours).

	Args:
	   dumpfile   (string): a gzipped wikidata json filename
	   h5filename (string): name of the HDF5 file name
	Kwargs:
	   lang     (string): language code of the language to extract
	Returns:
		a string, the name of the generated hdf5 table
	See also:  
		https://www.mediawiki.org/wiki/Wikibase/DataModel/JSON
	"""
	 
	igzstream     = bz2.open(dumpfile)
	savestream    = open(savefile,"w")
	
	def is_nlp_relevant(row):
		if row["id"][0] == "Q":
			return row['nlanguages'] > 0 and row['nsitelinks'] > 0 and row['nclaims'] > 0 and (row['is_instance'] or row['is_subclass'])
		else:
			return row['nlanguages'] > 0 and row['nclaims'] > 0 and (row['is_instance'] or row['is_subclass'])

	entity = igzstream.readline() #skip init 
	entity = igzstream.readline()
	eread = 0
	eadd = 0
	while entity:
		entity = entity.decode('utf-8')[:-2]
		if entity and entity[0] == '{':
			eread+=1
			try :
				entity = json.loads(entity)
				ent_id  = entity['id']
				entity['nclaims']     = len(entity['claims'].keys())    if 'claims'    in entity else 0
				entity['nlanguages']  = len(entity['labels'].keys())    if 'labels'    in entity else 0
				entity['nsitelinks']  = len(entity['sitelinks'].keys()) if 'sitelinks' in entity else 0
				entity['is_instance'] = 'P31'  in entity['claims']
				entity['is_subclass'] = 'P279' in entity['claims']
				if is_nlp_relevant(entity):
					eadd += 1
					savestream.write(str(entity))
					savestream.write("\n")
					if eadd % 100 == 0:
						print ('Added', eadd, 'entities','Read',eread,'entities',flush=True)
			except Exception as e:
				print('@@@',type(e),e)
							
		entity = igzstream.readline()
	igzstream.close()
	print('Reading done...')
	print ('Added', eadd, 'entities','Read',eread,'entities',flush=True)


if __name__ == '__main__':
	dumpname = "wikidata-2018-01-01.json.bz2"
	savefile = "result.json"
	extract_entities(dumpname, savefile, lang="fr")





