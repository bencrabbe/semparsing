#! /usr/bin/env python

"""
This module includes functions for calculating the pagerank for items of Wikidata via
a directed graph and for building a lexicon as a dictionnary.

(!) Time consuming and heavy ops due to large amounts of data.
Uses pytables (tables) as backend.    
"""

import gzip,bz2,json,sys,re
import urllib.request
#from lexer import DefaultLexer



def extract_entities(dumpfile,out_file,lang='fr'):
	"""
	Reads entities from a json.gz wikidata dump and filters out irrelevant entities.
	Stores the result in an HDF5 file

	That is an heavy operation (takes several hours).

	Args:
	   dumpfile      (string): a bzipped wikidata json filename
	Kwargs:
	   lang     (string): language code of the language to extract
	Returns:
		a string, the name of the generated hdf5 table
	See also:  
		https://www.mediawiki.org/wiki/Wikibase/DataModel/JSON
	"""

	# open the files
	#wikistream     = open(dumpfile)
	wikistream     = bz2.open(dumpfile)
	outstream      = open(out_file,"w")
	list_human = ['Q5','Q3658341','Q15773347','Q95074']
	
	def ishuman(entity):
		"""
		from an item get the directed graph (tuple of 3, 4 or 5 elements)
		"""
		if 'P31' in entity['claims'].keys():
			for mainsnak in entity['claims']['P31']:
				if "datavalue" in mainsnak["mainsnak"]: 
					if "value" in mainsnak["mainsnak"]["datavalue"]:
						if "id" in mainsnak["mainsnak"]["datavalue"]["value"] and type(mainsnak["mainsnak"]["datavalue"]["value"]) is dict:
							if mainsnak["mainsnak"]["datavalue"]["value"]["id"] in list_human:
								return True					
		return False

	# begin the processing of wikidata items
	eadd,eread = 0,0
	entity = wikistream.readline() #skip init 
	entity = wikistream.readline()
	while entity:
		#entity = entity[:-2]
		entity = entity.decode('utf-8')[:-2]
		if entity and entity[0] == '{':
			try :
				entity = json.loads(entity)

				if ishuman(entity):
					if 'en' in entity['labels']:
						dico_entity = {}
						dico_entity[entity['id']] = [entity['labels']['en']['value']]

						if lang in entity['labels']:
							dico_entity[entity['id']] = [entity['labels'][lang]['value']]
						if lang in entity['aliases']:
							dico_entity[entity['id']].extend([elt['value'] for elt in entity['aliases'][lang]])

						dico_entity[entity['id']] = list(set(dico_entity[entity['id']]))
						outstream.write(json.dumps(dico_entity) + "\n")

						eadd += 1
						if eadd % 10000 == 0:
							print ('Added', eadd, 'entities','Read',eread,'entities',flush=True)

				eread += 1

			except Exception as e:
				print('@@@',type(e),e)
							
		entity = wikistream.readline()
	
	wikistream.close()
	outstream.close()
	print('Reading done...')



if __name__ == '__main__':
	#dumpname = "wikidata-20180101-all.json"
	dumpname = "wikidata-20180101-all.json.bz2"
	out_file = "human_dico.json"
	extract_entities(dumpname,out_file,lang='fr')



