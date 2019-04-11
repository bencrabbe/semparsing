import gzip,bz2,json,sys,re
import urllib.request
from datetime import datetime
from tables import *
from lexer import DefaultBeamLexer


"""
This module manipulates the wikidata dump, extract the part
"""


class WikidataEntity(IsDescription):

    ent_idx     = StringCol(16)     # the Qxxx string identifier of the entity
    qlabels     = StringCol(4096)   # the label of the entity and its aliases 
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
     etable        = h5file.create_table(egroup, 'entities', WikidataEntity , "Entities stats",expectedrows=10000000)
     h5file.close()
     return h5filename

##########################################################################################
def get_graphe():
	"""
	this gets a graph from a 
	@param
	@return 
	"""
	pass


##########################################################################################
def get_graphe_avecP():
	pass