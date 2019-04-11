import json
import urllib.request
import networkx as nx
import numpy as np
import matplotlib.pyplot as plt

##########################################################################################
	

def get_graph(id_entity, nb_layer=2):
	"""
	this gets a graph from an id of a certain entity in wikidata
	@param id_entity : the id of the chosen entity
	@param nb_layer : the number of layers that we want, generally equals to 3
	@return (now) : only 1 list of tuples [(a,b),(c,d)...] which means a-->b, c-->d (a b c d : Q)

	@return (wish) : a list of 3 lists where 
		1. list of tuples [(a,b),(c,d)...] which means a-->b, c-->d (a b c d : Q)
		2. list of tuples [(a,b),(b,c)...] which means a-->b, b-->c (a c -> Q ; b -> P)
		3. list of tuples [(a,b),(b,c),(a,c)...] which means a-->b, b-->c, a-->c (a c -> Q ; b -> P)
	"""

	def add_entity(ent_idx, dic_entity):
		"""
		this adds the id of an entity and its content json of wikidata in a dictionnary if this entity 
		doesn't exist in the dictionnay
		"""
		if ent_idx not in dic_entity:
			entity_url = base_url.replace("$$$", ent_idx)
			dic_entity[ent_idx] = json.loads(urllib.request.urlopen(entity_url).read())

	def treat_jline(jline, graph):
		"""
		this treats an item of wikidata in form of json
		@param jline : 
		@param graph : 
		"""
		dic_entity = {}
		ent_idx = str(jline["entities"].keys())[12:-3] # id of the entity/relation
		claims = jline["entities"][ent_idx]["claims"]
		claims_keys = jline["entities"][ent_idx]["claims"].keys()
		for relation in claims_keys:
			for mainsnak in claims[relation]:
				if "datavalue" in mainsnak["mainsnak"]: 
					if "value" in mainsnak["mainsnak"]["datavalue"]:
						if "id" in mainsnak["mainsnak"]["datavalue"]["value"] and type(mainsnak["mainsnak"]["datavalue"]["value"]) is dict:
							right_part = (mainsnak["mainsnak"]["datavalue"]["value"]["id"])
							graph.add((ent_idx,relation,right_part))
							add_entity(ent_idx, dic_entity)
							add_entity(relation, dic_entity)
							add_entity(right_part, dic_entity)					

				if "qualifiers" in mainsnak:
					for qualifiers in mainsnak["qualifiers"]:
						if "datavalue" in mainsnak["qualifiers"][qualifiers][0]:
							if "value" in mainsnak["qualifiers"][qualifiers][0]["datavalue"]:
								if "id" in mainsnak["qualifiers"][qualifiers][0]["datavalue"]["value"] and type(mainsnak["qualifiers"][qualifiers][0]["datavalue"]["value"]) is dict:
									right_part2 = mainsnak["qualifiers"][qualifiers][0]["datavalue"]["value"]["id"]
									graph.add((ent_idx,relation,qualifiers,right_part2))
									add_entity(qualifiers, dic_entity)
									add_entity(right_part2, dic_entity)
		return dic_entity

	base_url = "https://www.wikidata.org/w/api.php?action=wbgetentities&ids=$$$&format=json"
	entity_url = base_url.replace("$$$",id_entity)
	dic_entity = {id_entity:json.loads(urllib.request.urlopen(entity_url).read())}
	dic_entity_temporary = {}
	graph = set()

	for i in range(nb_layer):
		for entity in dic_entity:
			dic_entity_temporary.update(treat_jline(dic_entity[entity], graph))
			print(len(dic_entity_temporary))
			print()
		dic_entity_temporary.update(dic_entity)
		print(len(dic_entity_temporary))
		print(len(dic_entity))
		dic_entity = {entity:dic_entity_temporary[entity] for entity in dic_entity_temporary if entity not in dic_entity}
		print(len(dic_entity))

	return (graph,dic_entity_temporary)

def convert_id2_entity(ent_idx, jline):
	return jline["entities"][ent_idx]["labels"]["en"]["value"]

def write_file(graph,dic_entity):
	fi = open("graph.txt","w")
	for g in graph:
		for elt in g:
			fi.write(elt)
			fi.write("\t")
		fi.write("\n")
	fi.close()

	fi = open("dic_entity.txt","w")
	for entity in dic_entity:
		fi.write(entity)
		fi.write("\t")
		fi.write(dic_entity[entity])
		fi.write("\n")
	fi.close()


if __name__ == '__main__':
	"""
	graph,dic_entity = get_graph("Q3244512", nb_layer=2)
	G = nx.DiGraph()

	for entity in dic_entity:
		dic_entity[entity] = convert_id2_entity(entity, dic_entity[entity])

	for g in graph:
		a = dic_entity[g[0]] + " (" + g[0] + ")"
		b = dic_entity[g[-1]] + " (" + g[-1] + ")"
		G.add_edge(a,b)

	nx.draw(G,with_labels=True)
	plt.savefig("examples.jpg")
	"""

	graph,dic_entity = get_graph("Q3244512", nb_layer=2)
	write_file(graph,dic_entity)



