#! /usr/bin/env python
from ast import literal_eval

def make_dico(graph_file, dico_file):
	dico1 = {}
	dico2 = {}
	dicofi = open(dico_file,"w")
	fi = open(graph_file)
	line = fi.readline()
	num = 1

	while line:
		line = line[:-1].split("\t")
		line = [x for g in line for x in literal_eval(g)]
		for x in line:
			if x not in dico1:
				if num % 100000 == 0:
					print ('Added', num, 'items in the dictionnary')
				dico1[x] = num 
				dico2[num] = x 
				num += 1 
		line = fi.readline()

		#except Exception as e:
		#	print('@@@',type(e),e)
	print("============================================================")
	print("in this dictionnary we have", num-1, "items")
	dicofi.write(str(dico1)+"\n")
	dicofi.write(str(dico2))
	print("dictionnary done")
	print("============================================================")


def make_graph(graph_file, out_file, dico_file, mode=1):
	fi = open(graph_file)
	sortie = open(out_file, "w")
	line = fi.readline()
	dicofi = open(dico_file).read().split("\n")
	dico1 = literal_eval(dicofi[0])
	graph = set()
	num = 1
	while line:
		line = line[:-1].split("\t")		
		line = [literal_eval(g) for g in line]
		for g in line:
			g = [str(dico1[x]) for x in g]
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
		if num % 10000 == 0:
			print ('Treated', num, 'items')
		num += 1
		line = fi.readline()
	fi.close()

	for a,b in graph:
		sortie.write(a + " " + b + "\n")

	sortie.close()
	print("============================================================")
	print("There are", num, "items whose graph have been converted")
	print("============================================================")

if __name__ == '__main__':
	graph_file = "graph-0424.txt"
	dico_file = "dico_e2c_c2e.txt"
	make_dico(graph_file, dico_file)

	out_file1 = "file2cpp_v1.txt"
	out_file2 = "file2cpp_v2.txt"
	
	make_graph(graph_file, out_file1, dico_file, mode=1)
	print("############################################################")
	print("##           preparation pagerank version 1 done          ##")
	print("############################################################")
	make_graph(graph_file, out_file2, dico_file, mode=2)
	print("############################################################")
	print("##           preparation pagerank version 2 done          ##")
	print("############################################################")
