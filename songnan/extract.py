#! /usr/bin/env python

import bz2,json,sys,re
from lexer import DefaultLexer

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

	print("read dict pagerank done")

	pr_dict = sorted(pr_dict.items(),key=lambda x:x[1], reverse=True)
	pr_dict = dict([(entity,i) for i,(entity,_) in enumerate(pr_dict)])

	"""
	print("==========================================================")
	for ent in pr_dict:
		print(ent,pr_dict[ent])
	print("==========================================================")
	"""	

	print("dict pagerank done")
	return pr_dict


def extract_entities(dumpfile,outfile,page_ranks,lang='fr'):
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
	outstream      = open(outfile,"w")

	# begin the processing of wikidata items
	eadd,eread = 0,0
	entity = wikistream.readline() #skip init 
	entity = wikistream.readline()
	while entity:
		entity = entity[:-2]
		#entity = entity.decode('utf-8')[:-2]
		if entity and entity[0] == '{':
			try :
				dict_entity = {}
				entity = json.loads(entity)

				if entity['id'] in page_ranks and 'en' in entity['labels']:
					dict_entity['id'] = entity['id']
					dict_entity['enlabel'] = entity['labels']['en']['value']
					dict_entity['order'] = page_ranks[entity['id']]


					if lang in entity['labels']:
						dict_entity['frlabel'] = entity['labels'][lang]['value']

					if lang in entity['aliases']:
						dict_entity['fraliase'] = [elt['value'] for elt in entity['aliases'][lang]]
					
					if entity['id'][0] == 'Q':
						dict_entity['bridging'] = [ bridge for bridge,order in sorted( [ (bridge,page_ranks[bridge]) for bridge in entity['claims'].keys() ], key=lambda x : x[1]) ]

					outstream.write(json.dumps(dict_entity)+"\n")

					eadd += 1
					if eadd % 10000 == 0:
						print ('Added', eadd, 'entities','Read',eread,flush=True)
				eread += 1
			except Exception as e:
				print('@@@',type(e),e)
							
		entity = wikistream.readline()
	
	wikistream.close()

	print('Reading done...')


def get_first_entities(jsonfilename,outfilename,max_size=1000000):
	jsonstream = open(jsonfilename)
	outstream = open(outfilename,"w")
	list_entities = []
	i = 0

	entity = jsonstream.readline()
	while entity:
		entity = json.loads(entity)
		if entity['order'] < max_size*1.5:
			list_entities.append(entity)

		entity = jsonstream.readline()

	jsonstream.close()
	list_entities = sorted(list_entities, key=lambda k: k['order'])[:max_size]

	for entity in list_entities:
		outstream.write(json.dumps(entity)+"\n")

	outstream.close()


def plural_en(word):
	if word.endswith('y'):
		return word[:-1] + 'ies'
	elif word[-1] in 'sx' or word[-2:] in ['sh', 'ch']:
		return word + 'es'
	elif word.endswith('an'):
		return word[:-2] + 'en'
	else:
		return word + 's'


def creat_variants(dico_labelaliases):
	set_result = set()
	# enlabel mini/majuscule
	set_result.update( [ dico_labelaliases['enlabel'],dico_labelaliases['enlabel'].lower(), dico_labelaliases['enlabel'].title(), dico_labelaliases['enlabel'].capitalize()] )
	# enlabel pluriel
	if len(dico_labelaliases['enlabel'].split())==1:
		set_result.add(plural_en(dico_labelaliases['enlabel']))
	# frlabel mini/majuscule
	if 'frlabel' in dico_labelaliases:
		set_result.update( [ dico_labelaliases['frlabel'],dico_labelaliases['frlabel'].lower(), dico_labelaliases['frlabel'].title(), dico_labelaliases['frlabel'].capitalize()] )
	# frlabel pluriel

	# fraliase mini/majuscule
	if 'fraliase' in dico_labelaliases:
		set_result.update(dico_labelaliases['fraliase'])
		set_result.update([aliase.lower() for aliase in dico_labelaliases['fraliase']])
		set_result.update([aliase.title() for aliase in dico_labelaliases['fraliase']])
		set_result.update([aliase.capitalize() for aliase in dico_labelaliases['fraliase']])
	# fraliase pluriel

	return set_result

def make_dictionary(first_entfilename):
	"""
	Builds the dictionary from an entity list.
	For a given entry, entities are sorted according to elist's order
	Args: 
	   h5filename (string): the name of the HF5 file as a string
	   max_size (unsigned): the max number of entities in the dictionary
	Return:
	   a python dictionary string -> ordered list of Qxxx IDs
	 """
	entfilestream = open(first_entfilename) 
	stop_words = ['Q2865743','P585','Q397','Q744346','Q2865743','Q684','Q33350','Q1811','Q33947','Q188', 'P642','Q1801','Q27956604','Q131068','Q850088','Q2559220','Q1385','Q208141','Q897','Q66254','Q758379','Q506881','Q261494','Q279014','Q876','Q6452640','Q20085828','Q42614']

	D   = { }
	dico_bridging = { }

	entity = entfilestream.readline()
	while entity:
		try:
			entity = json.loads(entity)
			idx    = entity['id']

			if idx not in stop_words:
				if 'bridging' in entity:
					dico_bridging[idx] = entity['bridging']
				elif idx[0]=='P':
					dico_bridging[idx] = []
				else:
					print("keyerror bridge===================",idx,"===================")

				labels = {}
				labels['enlabel'] = entity['enlabel']
				if 'frlabel' in entity:
					labels['frlabel'] = entity['frlabel']
				if 'fraliase' in entity:
					labels['fraliase'] = entity['fraliase']	
				
				labels = creat_variants(labels)

				for lbl in labels:
					if any(c.isalnum() for c in lbl) and not re.search(r'\*|\+|\(|\)|\[|\]|\?|\\',lbl): #throws away irreg labels (containing regex reserved chars) 
						if lbl in D:
							D[lbl].append(idx)
						else:
							D[lbl] = [idx]

			entity = entfilestream.readline()

		except Exception as e:
			print('@@@',type(e),e)
	
	#normalize dict keys
	lex = DefaultLexer('strong-cpd.dic')
	D = dict([ ( ' '.join([ent for ent,_ in lex.tokenize_line(key)]) , value) for key,value in D.items()])
	print("make dico done")
	return (D,dico_bridging)


def dump_dictionary(D,dico_bridging,dictfilename='entities_dict.json'):
	"""
	Dumps a dictionary to stream
	"""
	i = 0
	one_part = int(len(D)/100)
	ofile = open(dictfilename,'w') 
	for key,val in D.items( ):
		ofile.write(json.dumps({'named_entity':key, 'entity_list':{qidx:dico_bridging[qidx] for qidx in val}})+"\n")
		i+=1
		if i%one_part == 0:
			print("process ",int(i/one_part),"%")
	ofile.close()


if __name__ == '__main__':
	#dumpname = "wikidata-20180101-all.json"
	#dumpname = "wikidata-20180101-all.json.bz2"

	"""
	prfilename1 = "pagerank_v1.txt"
	outfile1 = "dico_entities_1.json"
	pr_dict1 = page_rank_dict(prfilename1)
	extract_entities(dumpname, outfile1, pr_dict1, lang="fr")
	"""

	"""
	prfilename2 = "pagerank_v2.txt"
	outfile2 = "dico_entities_2.json"
	pr_dict2 = page_rank_dict(prfilename2)
	extract_entities(dumpname, outfile2, pr_dict2, lang="fr")
	"""

	"""
	jsonfilename1 = "dico_entities_1.json"
	outfilename1 = "1m_ent_1.json"
	get_first_entities(jsonfilename1,outfilename1,max_size=1000000)
	print("extract 1 million first entities done (ordered, version 1)")
	"""
	"""
	jsonfilename2 = "dico_entities_2.json"
	outfilename2 = "1m_ent_2.json"
	get_first_entities(jsonfilename2,outfilename2,max_size=1000000)
	print("extract 1 million first entities done (ordered, version 2)")
	"""
	
	"""
	dictfilename1 = "entities_dict1.json"
	D1, dico_bridging1 = make_dictionary("1m_ent_1.json")
	dump_dictionary(D1, dico_bridging1, dictfilename1)
	print("dump dico1 done")
	dictfilename2 = "entities_dict2.json"
	D2, dico_bridging2 = make_dictionary("1m_ent_2.json")
	dump_dictionary(D2, dico_bridging2, dictfilename2)
	print("dump dico2 done")
	"""

	dictfilename1 = "dico_quan1.json"
	D1, dico_bridging1 = make_dictionary("1m_ent_1.json")
	dump_dictionary(D1, dico_bridging1, dictfilename1)
	print("dump dico1 done")
	dictfilename2 = "dico_quan2.json"
	D2, dico_bridging2 = make_dictionary("1m_ent_2.json")
	dump_dictionary(D2, dico_bridging2, dictfilename2)
	print("dump dico2 done")

