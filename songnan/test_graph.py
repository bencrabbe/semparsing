import json
import urllib.request
import networkx as nx
import numpy as np
import matplotlib.pyplot as plt

class Graph:
	def __init__(self, nodes):
		self.nodes = nodes
		self.adj = {node:[] for node in nodes}
		self.incid = {node:set() for node in nodes}
	def add_edge(self, s, t):
		self.adj[s].append(t)
		self.incid[t].add(s)
	def neighbors(self,node):
		return self.adj[node]
	def incidents(self,node):
		return list(self.incid[node])

def get_graph_1(id_entity):

	def treat_jline(jline):
		"""
		this treats an item of wikidata in form of json
		@param jline : 
		@param graph : 
		"""
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
							set_entity.add(ent_idx)
							set_entity.add(relation)
							set_entity.add(right_part)				

				if "qualifiers" in mainsnak:
					for qualifiers in mainsnak["qualifiers"]:
						if "datavalue" in mainsnak["qualifiers"][qualifiers][0]:
							if "value" in mainsnak["qualifiers"][qualifiers][0]["datavalue"]:
								if "id" in mainsnak["qualifiers"][qualifiers][0]["datavalue"]["value"] and type(mainsnak["qualifiers"][qualifiers][0]["datavalue"]["value"]) is dict:
									right_part2 = mainsnak["qualifiers"][qualifiers][0]["datavalue"]["value"]["id"]
									graph.add((ent_idx,relation,qualifiers,right_part2))
									set_entity.add(ent_idx)
									set_entity.add(relation)
									set_entity.add(qualifiers)
									set_entity.add(right_part2)

	base_url = "https://www.wikidata.org/w/api.php?action=wbgetentities&ids=$$$&format=json"
	entity_url = base_url.replace("$$$",id_entity)
	graph = set()
	set_entity = set()
	treat_jline(search_entity(entity_url))

	return (graph,set_entity)	




def get_graph_2(id_entity):

	def treat_jline(jline):
		"""
		this treats an item of wikidata in form of json
		@param jline : 
		@param graph : 
		"""
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
							set_entity.add(ent_idx)
							set_entity.add(relation)
							set_entity.add(right_part)				

				if "qualifiers" in mainsnak:
					for qualifiers in mainsnak["qualifiers"]:
						if "datavalue" in mainsnak["qualifiers"][qualifiers][0]:
							if "value" in mainsnak["qualifiers"][qualifiers][0]["datavalue"]:
								if "id" in mainsnak["qualifiers"][qualifiers][0]["datavalue"]["value"] and type(mainsnak["qualifiers"][qualifiers][0]["datavalue"]["value"]) is dict: 
									right_part2 = mainsnak["qualifiers"][qualifiers][0]["datavalue"]["value"]["id"]
									graph.add((ent_idx,relation,qualifiers,right_part2))
									set_entity.add(ent_idx)
									set_entity.add(relation)
									set_entity.add(qualifiers)
									set_entity.add(right_part2)

	base_url = "https://www.wikidata.org/w/api.php?action=wbgetentities&ids=$$$&format=json"
	entity_url = base_url.replace("$$$",id_entity)
	graph = set()
	set_entity = set()
	treat_jline(search_entity(entity_url))

	i = 1
	set_entity_tempo = set_entity.copy()
	print(len(set_entity_tempo))
	for entity in set_entity_tempo:
		treat_jline(search_entity(entity))
		print(i)
		i+=1

	return (graph,set_entity)	



def search_entity(ent_idx):
	base_url = "https://www.wikidata.org/w/api.php?action=wbgetentities&ids=$$$&format=json"
	entity_url = base_url.replace("$$$", ent_idx)
	return json.loads(urllib.request.urlopen(entity_url).read())

def convert_id2_entity(ent_idx):
	jline = search_entity(ent_idx)
	if "en" in jline["entities"][ent_idx]["labels"] and type(jline["entities"][ent_idx]["labels"]) is dict:
		return jline["entities"][ent_idx]["labels"]["en"]["value"]
	else:
		return "UNK"


##########################################################################################

class PRIterator:

	def __init__(self, dg):
		self.damping_factor = 0.85 
		self.max_iterations = 100  
		self.min_delta = 0.00001  
		self.graph = dg

	def page_rank(self):

		nodes = self.graph.nodes
		graph_size = len(nodes)

		if graph_size == 0:
			return {}
		page_rank = dict.fromkeys(nodes, 1.0 / graph_size)  # initial PR
		damping_value = (1.0 - self.damping_factor) / graph_size  # (1−α)/N

		flag = False
		for i in range(self.max_iterations):
			change = 0
			for node in nodes:
				rank = 0
				#print(self.graph.incidents(node))
				for incident_page in self.graph.incidents(node):  # 遍历所有“入射”的页面
					rank += self.damping_factor * (page_rank[incident_page] / len(self.graph.neighbors(incident_page)))
				rank += damping_value
				change += abs(page_rank[node] - rank)  # 绝对值
				page_rank[node] = rank

			#print("This is NO.%s iteration" % (i + 1))
			#print(page_rank)

			if change < self.min_delta:
				flag = True
				break
		if flag:
			print("finished in %s iterations!" % node)
		else:
			print("finished out of 100 iterations!")
		return page_rank



if __name__ == '__main__':
	"""
	graph,set_entity = get_graph_2("Q3244512")
	G = nx.DiGraph()
	print(len(set_entity))
	print(len(graph))
	
	#dic_entity = {}
	#for entity in set_entity:
	#	dic_entity[entity] = convert_id2_entity(entity)
	#print("dico fini")
	
	gr = []
	for g in graph:
		#a = dic_entity[g[0]] + " (" + g[0] + ")" # Q1
		#b = dic_entity[g[-1]] + " (" + g[-1] + ")" # Q2
		#c = dic_entity[g[1]] + " (" + g[1] + ")" # P
		a = g[0]
		b = g[-1]
		c = g[1]
		#gr.append((a,c))
		#gr.append((c,b))
		gr.append((a,b))

	#G.add_edges_from(gr)
	G.add_edges_from(gr)

	plt.figure(figsize=(14.2, 24.2)) 
	nx.draw(G,with_labels=True)
	plt.savefig("examples.jpg")
	"""

	list_graph, nodes = get_graph_2("Q3244512")
	dg = Graph(list(nodes))
	for x in list_graph:
		dg.add_edge(x[0],x[-1])
		#dg.add_edge(x[0],x[1])
		#dg.add_edge(x[1],x[-1])

	pr = PRIterator(dg)
	page_ranks = pr.page_rank()
	page_ranks = sorted(page_ranks.items(),key=lambda item:item[1], reverse=True)
	fi = open("pr.txt","w")
	for cle,valeur in page_ranks:
		fi.write(cle)
		fi.write("\t")
		fi.write(str(valeur))
		fi.write("\n")
