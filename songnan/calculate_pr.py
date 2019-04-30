#! /usr/bin/env python

"""
This module includes functions for calculating the pagerank for items of Wikidata via
a directed graph and for building a lexicon as a dictionnary.

(!) Time consuming and heavy ops due to large amounts of data.
Uses pytables (tables) as backend.    
"""



# Copyright (c) 2010, Panos Louridas, GRNET S.A.
#
#  All rights reserved.
# 
#  Redistribution and use in source and binary forms, with or without
#  modification, are permitted provided that the following conditions
#  are met:
#
#  * Redistributions of source code must retain the above copyright
#  notice, this list of conditions and the following disclaimer.
#
#  * Redistributions in binary form must reproduce the above copyright
#  notice, this list of conditions and the following disclaimer in the
#  documentation and/or other materials provided with the
#  distribution.
#
#  * Neither the name of GRNET S.A, nor the names of its contributors
#  may be used to endorse or promote products derived from this
#  software without specific prior written permission.
# 
#  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
#  "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
#  LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
#  FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
#  COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT,
#  INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
#  (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
#  SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
#  HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
#  STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
#  ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED
#  OF THE POSSIBILITY OF SUCH DAMAGE.



import gzip,bz2,json,sys,re
import urllib.request
from datetime import datetime
from tables import *
#from lexer import DefaultLexer
from ast import literal_eval
import sys
from pageRank import pageRank


class WikidataEntity(IsDescription):

	ent_idx     = StringCol(16)     # the Qxxx string identifier of the entity
	qlabels     = StringCol(9000)   # the label of the entity and its aliases 
	nclaims     = Int64Col()        # the number of claims for the entity
	nlanguages  = Int64Col()        # the number of languages for the entity
	nsitelinks  = Int64Col()        # the number of sitelinks for the entity
	is_instance = BoolCol()         # states if entity isa P31 
	is_subclass = BoolCol()         # states if entity ako P279
	neg_page_rank   = Float64Col()  # provides the negative page rank of an entity (! set to 0 for properties)

	

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
	   dumpfile      (string): a bzipped wikidata json filename
	   h5filename    (string): name of the HDF5 file name
	   graphfilename (string): name of the graph file name to store the graph
	Kwargs:
	   lang     (string): language code of the language to extract
	Returns:
		a string, the name of the generated hdf5 table
	See also:  
		https://www.mediawiki.org/wiki/Wikibase/DataModel/JSON
	"""

	# open the files
	wikistream     = open(dumpfile)
	h5file        = open_file(h5filename, mode="a")
	graphfi       = open(graphfilename,"w")
	etable        = h5file.root.dbgroup.entities
	
	def is_nlp_relevant(row):
		"""
		test if the item is valid or not (we only process valid ones)
		"""
		if row['ent_idx'][0] == "Q":
			return row['nlanguages'] > 0 and row['nsitelinks'] > 0 and row['nclaims'] > 0 and (row['is_instance'] or row['is_subclass'])
		else:
			return row['nlanguages'] > 0 and row['nclaims'] > 0 and (row['is_instance'] or row['is_subclass'])
	
	def get_graph(entity):
		"""
		from an item get the directed graph (tuple of 3, 4 or 5 elements)
		"""
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

	# begin the processing of wikidata items
	tptr   = etable.row
	eadd,eread = 0,0
	maxlblL = 0
	entity = wikistream.readline() #skip init 
	entity = wikistream.readline()
	while entity:
		entity = entity[:-2]
		if entity and entity[0] == '{':
			try :
				entity = json.loads(entity)
				if 'en' in entity['labels']:
					qlabel = [ entity['labels']['en']['value'] ]
					if lang in entity['labels']:
						qlabel.extend([ entity['labels'][lang]['value'] ])
					if lang in entity['aliases']:
						qlabel.extend( [elt['value'] for elt in entity['aliases'][lang]] )
					qlabel = list(set(qlabel))
					qlabel = ';'.join(qlabel).encode('utf-8') #use foo.decode('utf-8') when getting values out of the table
					maxlblL = max(maxlblL, len(qlabel))

					tptr['ent_idx']     = entity['id']  
					tptr['qlabels']     = qlabel      
					tptr['nclaims']     = len(entity['claims'].keys())    if 'claims'    in entity else 0
					tptr['nlanguages']  = len(entity['labels'].keys())    if 'labels'    in entity else 0
					tptr['nsitelinks']  = len(entity['sitelinks'].keys()) if 'sitelinks' in entity else 0
					tptr['is_instance'] = 'P31'  in entity['claims']
					tptr['is_subclass'] = 'P279' in entity['claims']
					#tptr['neg_page_rank']= -page_ranks.get(ent_id,0.0)

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
							
		entity = wikistream.readline()
	
	wikistream.close()
	etable.flush()
	#etable.cols.neg_page_rank.create_csindex() 

	h5file.close()
	print('Reading done...')


def make_dico(graphfilename, dicoidx_file):
	dico_i2c = {}
	list_c2i = set()
	dicofi = open(dicoidx_file,"w")
	fi = open(graphfilename)
	line = fi.readline()

	while line:
		line = line[:-1].split("\t")
		line = [x for g in line for x in literal_eval(g)]
		for x in line:
			list_c2i.add(x)			
		line = fi.readline()
	fi.close()

	list_c2i = list(list_c2i)
	dico_i2c = dict(zip(list_c2i,range(len(list_c2i))))

	print("============================================================")
	print("in this dictionnary we have", len(list_c2i), "items")
	dicofi.write(str(dico_i2c)+"\n")
	dicofi.write(' '.join(list_c2i))
	dicofi.close()
	print("dictionnary done")
	print("============================================================")
	return (dico_i2c, list_c2i)



def make_graph(graphfilename, out_file, dico_i2c, mode=1):
	"""
	from the graph file created by the function extract_entities,

	"""
	graphfi = open(graphfilename)
	sortie = open(out_file, "w")
	
	line = graphfi.readline()
	graph = set()
	num = 0
	while line:
		line = line[:-1].split("\t")		
		line = [literal_eval(g) for g in line]
		for g in line:
			g = [str(dico_i2c[x]) for x in g]
			if mode==1:
				if len(g) == 3:
					graph.update([(g[0],g[1]),(g[1],g[2])])
				elif len(g) == 4:
					graph.update([(g[0],g[1]),(g[1],g[2]),(g[2],g[3])])
				else:
					graph.update([(g[0],g[1]),(g[1],g[2]),(g[2],g[3]),(g[3],g[4])])
			else:
				if len(g) == 3:
					graph.update([(g[0],g[1]),(g[1],g[2]),(g[0],g[2])])
				elif len(g) == 4:
					graph.update([(g[0],g[1]),(g[1],g[2]),(g[2],g[3]),(g[0],g[3])])
				else:
					graph.update([(g[0],g[1]),(g[1],g[2]),(g[2],g[3]),(g[3],g[4]),(g[0],g[2]),(g[0],g[4]),(g[2],g[4])])
		num += 1
		if num % 10000 == 0:
			print ('Treated', num, 'items which have a graph')
		line = graphfi.readline()
	graphfi.close()

	for a,b in graph:
		sortie.write(a + " " + b + "\n")
	sortie.close()

	print("============================================================")
	print("There are", num, "items whose graph have been converted")
	print("============================================================")


def calculate_pagerank(out_file, list_c2i, prfilename):
	links = [[]]
	
	f = open(out_file)
	for line in f:
		(frm, to) = map(int, line.split(" "))
		extend = max(frm - len(links), to - len(links)) + 1
		for i in range(extend):
			links.append([])
		links[frm].append(to)
	f.close()

	pr =  pageRank(links, alpha=0.85, convergence=0.00001, checkSteps=10)
	fi = open(prfilename,"w")

	for i in range(len(pr)):
		fi.write(list_c2i[i] + "\t" + str(pr[i]) + "\n")

	print("calculate pagerank over for the file " + prfilename)


if __name__ == '__main__':
	dumpname = "wikidata-20180101-all.json"
	#h5filename = create_wikidata_subsetfile(dumpname)
	graphfilename = "graph-0430.txt"

	h5filename = "wikidata-20180101-all.h5"
	extract_entities(dumpname, h5filename, graphfilename, lang="fr")

	dicoidx_file = "dico_e2c_c2e.txt"
	dico_i2c, list_c2i = make_dico(graphfilename, dicoidx_file)
	out_file1 = "file2pr_v1.txt"
	out_file2 = "file2pr_v2.txt"

	make_graph(graphfilename, out_file1, dico_i2c, mode=1)
	print("############################################################")
	print("##           preparation pagerank version 1 done          ##")
	print("############################################################")
	make_graph(graphfilename, out_file2, dico_i2c, mode=2)
	print("############################################################")
	print("##           preparation pagerank version 2 done          ##")
	print("############################################################")

	prfilename1 = "pagerank_v1.txt"
	prfilename2 = "pagerank_v2.txt"
	calculate_pagerank(out_file1, list_c2i, prfilename1)
	calculate_pagerank(out_file2, list_c2i, prfilename2)
	print("all finished")
	
	












