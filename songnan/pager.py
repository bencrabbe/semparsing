import gzip,bz2,json,sys,re
from ast import literal_eval

def transfer_num2idx(dico_filename):
	dicostream = open(dico_filename)
	dico_c2e = dicostream.readline()
	dico_c2e = dicostream.readline()
	dico_c2e = literal_eval(dico_c2e)
	print("read dictionnary done")
	return dico_c2e


def transfer_pagerank(pagerankfilename, dico_c2e, outputfilename):
	"""
	Reads in the content of the bzipped2 page rank file
	and returns a dict : entity -> rank
	"""
	prstream = open(pagerankfilename)
	outputstream = open(outputfilename, "w")

	for line in prstream:
		if line:
			try:
				idx,page_rank = line.split(" ")
				outputstream.write(dico_c2e[idx] + " " + page_rank + "\n")
			except Exception as e:
				print('@@@',type(e),e)
				
	prstream.close()
	print("pagerank file transfered")



if __name__ == '__main__':   
	dico_filename = "dico_e2c_c2e.txt"
	dico_c2e = transfer_num2idx(dico_filename)
	
	pagerankfilename1 = 'pr_v1.txt'
	pagerankfilename2 = 'pr_v2.txt'
	
	outputfilename1 = "pagerank_v1.txt"
	outputfilename2 = "pagerank_v2.txt"

	transfer_num2idx(pagerankfilename1, dico_c2e, outputfilename1)
	transfer_num2idx(pagerankfilename2, dico_c2e, outputfilename2)
