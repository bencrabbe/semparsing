#! /usr/bin/env python

import gzip,bz2,json,sys,re
from tables import *
from lexer import DefaultLexer


class WikidataEntity(IsDescription):

	ent_idx     = StringCol(16)     # the Qxxx string identifier of the entity
	qlabels     = StringCol(9000)   # the label of the entity and its aliases 
	neg_page_rank   = Float64Col()  # provides the negative page rank of an entity (! set to 0 for properties)
	bridging    = StringCol(1000)


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



def extract_entities(dumpfile,h5filename,page_ranks,lang='fr'):
	"""
	Reads entities from a json.gz wikidata dump and filters out irrelevant entities.
	Stores the result in an HDF5 file

	That is an heavy operation (takes several hours).

	Args:
	   dumpfile      (string): a bzipped wikidata json filename
	   h5filename    (string): name of the HDF5 file name
	Kwargs:
	   lang     (string): language code of the language to extract
	Returns:
		a string, the name of the generated hdf5 table
	See also:  
		https://www.mediawiki.org/wiki/Wikibase/DataModel/JSON
	"""

	# open the files
	wikistream    = open(dumpfile)
	#wikistream     = bz2.open(dumpfile)
	h5file        = open_file(h5filename, mode="a")
	etable        = h5file.root.dbgroup.entities

	# begin the processing of wikidata items
	tptr   = etable.row
	eadd,eread = 0,0
	maxlblL = 0
	maxbridge = 0
	entity = wikistream.readline() #skip init 
	entity = wikistream.readline()
	while entity:
		entity = entity[:-2]
		#entity = entity.decode('utf-8')[:-2]
		if entity and entity[0] == '{':
			try :
				entity = json.loads(entity)
				if entity['id'] in page_ranks and 'en' in entity['labels']:
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
					tptr['neg_page_rank']= -page_ranks.get(entity['id'],0.0)
					if entity['id'][0] == 'Q':
						tptr['bridging']    = ";".join(entity['claims'].keys()).encode('utf-8')
						maxbridge = max(maxbridge, len(tptr['bridging']))
					tptr.append()

					eadd += 1
					if eadd % 10000 == 0:
						print ('Added', eadd, 'entities','Read',eread,'entities','Max label length (in bytes)',maxlblL,'Max bridging length (in bytes)',maxbridge,flush=True)
				eread += 1
			except Exception as e:
				print('@@@',type(e),e)
							
		entity = wikistream.readline()
	
	wikistream.close()
	etable.flush()
	etable.cols.neg_page_rank.create_csindex() 

	h5file.close()
	print('Reading done...')



def page_rank_dict(pagerankfilename):
	"""
	Reads in the content of the page rank file
	and returns a dict : entity -> rank
	"""
	pr_dict = {}
	prstream = open(pagerankfilename)
	for line in prstream:
		ent_idx, page_rank = line.split()
		pr_dict[ent_idx] = float(page_rank) 
	prstream.close()
	return pr_dict



def make_dictionary(h5filename,max_size=1000000):
	"""
	Builds the dictionary from an entity list.
	For a given entry, entities are sorted according to elist's order
	Args: 
	   h5filename (string): the name of the HF5 file as a string
	   max_size (unsigned): the max number of entities in the dictionary
	Return:
	   a python dictionary string -> ordered list of Qxxx IDs
	 """
	h5file        = open_file(h5filename, mode="a") 
	etable        = h5file.root.dbgroup.entities 
	 
	D   = { }
	dico_bridging = { }
	i = 0 
	for entity in etable:  #increasing negative order	<=> decreasing page rank order

		labels = entity['qlabels'].decode('utf-8').split(';')
		idx    = entity['ent_idx'].decode('ascii')
		dico_bridging[idx] = entity['bridging'].decode('utf-8').split(';')

		if i < max_size:       
			for lbl in labels:
				if any(c.isalnum() for c in lbl) and not re.search(r'\*|\+|\(|\)|\[|\]|\?|\\',lbl): #throws away irreg labels (containing regex reserved chars) 
					if lbl in D:
						D[lbl].append(idx)
					else:
						D[lbl] = [idx]
		i += 1
	h5file.close() 
	
	#normalize dict keys
	#lex = DefaultLexer('strong-cpd.dic')
	#D = dict([ ( ' '.join(lex.tokenize_line(key)) , value) for key,value in D.items()])
	
	return (D,dico_bridging)


def dump_dictionary(D,dico_bridging,dictfilename='entities_dict.txt'):
	"""
	Dumps a dictionary to stream
	"""
	ofile = open(dictfilename,'w') 
	for key,val in D.items( ):
		#print(key,':::',';'.join( [qidx for qidx in val]),':::',';'.join( [bridge for qidx in val for bridge in dico_bridging[qidx]] ),file=ofile )
		print(key, ':::', '$$$'.join(['@@@'.join([qidx,';'.join(dico_bridging[qidx])]) for qidx in val]),file=ofile)
	ofile.close()




if __name__ == '__main__':
	prfilename1 = "pagerank_v1.txt"
	pr_dict1 = page_rank_dict(prfilename1)
	dumpname = "wikidata-20180101-all1.json"
	
	#h5filename1 = create_wikidata_subsetfile(dumpname)
	
	
	h5filename1 = "wikidata-20180101-all1.h5"
	extract_entities(dumpname, h5filename1, pr_dict1, lang="fr")
	D1, dico_bridging = make_dictionary(h5filename1, max_size=2000)
	dump_dictionary(D1,dico_bridging,dictfilename='entities_dict1.txt')
	print("dump dic1 done")
	



	"""
	d = {'1': ['2', '3'], '4': ['5', '6', '7']}
	dico_bridging = {'2':['8','9','10'],'3':['11','12'],'5':['1'],'6':['3','4'],'7':['1']}
	
	1 ::: 2@@@8;9;10$$$3@@@11;12
	4 ::: 5@@@1$$$6@@@3;4$$$7@@@1
	"""



