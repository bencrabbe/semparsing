import sys
from math import exp,log
from functional_core import *
from lambda_parser import FuncParser
from wikidata_model import WikidataModelInterface, NamingContextWikidata,Assignation
#from lexer import DefaultLexer
from lexerpytrie_quan import DefaultLexer
from SparseWeightVector import SparseWeightVector
from constree import ConsTree

def read_LF_dictionary(filename):
    """
    This reads in the Logical form dictionary
    @param filename the dictionary file
    @return a dict :  name -> lambda term
    """ 
    wikidata_model = WikidataModelInterface()
    wikidata_names = NamingContextWikidata.make_wikidata_builtins_context(debug=True)
    parser = FuncParser(wikidata_names,wikidata_model)

    lfdic = {}
    istream = open(filename)
    for line in istream:
        parser.parse_code(line)
        lfdic[parser.last_defined_macro] =  parser.last_defined_term 
    istream.close()
    return lfdic

class ParseFailureError(Exception) :

    def __init__(self,nD,sumZ,toklist):
        self.nD      = nD
        self.sumZ    = sumZ
        self.toklist = toklist

    def __str__(self):
        return 'parse failure error. num derivations %d; Z = %f\n==>%s'%(self.nD,self.sumZ,'+'.join([str(tok.form) for tok in self.toklist]))
        
class SRAction:

    
    APPLY_LEFT  = '>'
    APPLY_RIGHT = '<'
    SHIFT       = 'S'
    DROP        = 'D'
    SHIFT_UNARY = 'U' #performs a shift and applies an unary combinator on the lambda-term
    COORD       = 'C'
    #LEFT        = 'L'
    #RIGHT       = 'R'
    #UNARY       = 'U'
    #NO_ACTION   = 'N'
     
    def __init__(self,act_type,act_macro=None,act_combinator=None):
         
        self.act_type       = act_type
        self.act_macro      = act_macro
        self.act_combinator = act_combinator

        #combinator type
        self.ctype = TypeSystem.typecheck(self.act_combinator) if self.act_combinator else None
        
        #label pushed on the stack and used as feature input by the CRF.
        self.stack_label = "%s[%s]"%(act_type,act_macro) if act_macro else act_type

    def logical_apply(self,lhs,rhs):
        """
        Performs one step of compositional LF construction.
        @param lhs : a lambda term
        @param rhs : a lambda term 
        @return    : a lambda term
        """ 
        if self.act_type in [ SRAction.APPLY_LEFT,SRAction.COORD ]:
            if self.act_combinator:
                return LambdaApplication( LambdaApplication(self.act_combinator.copy(),lhs) , rhs )
            else:
                return LambdaApplication( lhs , rhs )
        elif self.act_type == SRAction.APPLY_RIGHT:
            if self.act_combinator:
                return LambdaApplication( LambdaApplication(self.act_combinator.copy(),rhs) , lhs )
            else:
                return LambdaApplication( rhs , lhs )
        elif self.act_type == SRAction.SHIFT_UNARY:
            return  LambdaApplication(self.act_combinator.copy(), lhs)                  
        
        print('apply oops',self.stack_label)
  
    def logical_type( self,lhs_type,rhs_type=TypeSystem.FAILURE ):
        """
        @param lhs_type: type of the left operand
        @param rhs_type: type of the right operand
        @return the type of the return value
        """
        if self.act_type in [ SRAction.APPLY_LEFT, SRAction.COORD ]:
            if self.act_combinator:
                lhs_type = TypeSystem.deduce_application_type(self.ctype,lhs_type)
            return TypeSystem.deduce_application_type(lhs_type,rhs_type)
        elif self.act_type ==  SRAction.APPLY_RIGHT:
            if self.act_combinator:
                rhs_type = TypeSystem.deduce_application_type(self.ctype,rhs_type)
            return TypeSystem.deduce_application_type(rhs_type,lhs_type)
        elif self.act_type == SRAction.SHIFT_UNARY:
            return TypeSystem.deduce_application_type(self.ctype,lhs_type)    
        print('type oops',self.stack_label)
       
    def head(self,lhs,rhs=None,coord=None):
        """
        @param lhs : the head index of the left operand
        @param rhs : the head index of the right operand
        @return the head index from the two operand lhs / rhs
        """
        if self.act_type   == SRAction.APPLY_LEFT:
            return lhs
        elif self.act_type == SRAction.APPLY_RIGHT:
            return rhs
        elif self.act_type == SRAction.SHIFT:
            return lhs
        elif self.act_type == SRAction.SHIFT_UNARY:
            return lhs
        elif self.act_type == SRAction.COORD:
            return coord
        else:
            print('oops missing action, not handled by head : ',self.act_type)
            return None
        
    def __str__(self):
        if self.act_macro:
            return '%s(%s)'%(self.act_type, self.act_macro)
        else:
            return self.act_type


class StackElement:
    """
    Type of elements pushed on the stack
    """
    def __init__(self,label,head_idx,logical_type):
        self.label        = label
        self.head_idx     = head_idx
        self.logical_type = logical_type
        
    def __str__(self):
        return '%s[%d]'%(self.label,self.head_idx)
            
    def copy(self):
        return StackElement(self.label,self.head_idx,self.logical_type)

    
class BeamCell:

    __slots__ = ['prev', 'action','config']
    
    def __init__(self,prev_cell,action,config):
        self.prev   = prev_cell
        self.action = action
        self.config = config

        
    def init_element(config):
        """
        Generates the beam initial (root) element
        Args:
           config (tuple): the parser init config
        Returns:
           BeamElement to be used at init
        """
        return BeamCell(None,None,config)
    
    def is_initial_element(self):
        """
        Returns:
            bool. True if the element is root of the beam
        """
        return self.prev is None or self.action is None

    
class CCGParser :
    """
    That's a CCG style robust shift reduce parser (arc standard style)
    with CRF style statistical inference. 
    """
    def __init__(self,lexer):
        
        self.actions_list = self.make_actions()  #records an ordering of parsing actions           
        self.weights      = SparseWeightVector() 
        self.lexer        = lexer
        
    def make_actions(self):
        """
        Builds the list of actions of this parser
        @return a list of SRAction instances
        """
        wikidata_model = WikidataModelInterface()
        wikidata_names = NamingContextWikidata.make_wikidata_builtins_context(debug=True)
        logical_parser = FuncParser(wikidata_names,wikidata_model)

        actions = [SRAction(SRAction.SHIFT),SRAction(SRAction.APPLY_LEFT),SRAction(SRAction.APPLY_RIGHT),\
                       SRAction(SRAction.DROP), SRAction(SRAction.SHIFT_UNARY)]

        logical_parser.parse_code("(define SWAP (lambda (P:e=>e=>t x:e y:e)  (P y x)))")
        actions.append(SRAction(SRAction.SHIFT_UNARY,act_macro=logical_parser.last_defined_macro,act_combinator=logical_parser.last_defined_term))
         
        logical_parser.parse_code("(define JOIN (lambda (P:e=>e=>t Q:e=>t x:e) (exists (y:e) (and (P x y) (Q y)))))")
        actions.append(SRAction(SRAction.APPLY_LEFT,act_macro=logical_parser.last_defined_macro,act_combinator=logical_parser.last_defined_term))
        actions.append(SRAction(SRAction.APPLY_RIGHT,act_macro=logical_parser.last_defined_macro,act_combinator=logical_parser.last_defined_term))

        logical_parser.parse_code("(define AND (lambda (P:e=>t Q:e=>t x:e) (and (P x) (Q x))))")
        actions.append(SRAction(SRAction.COORD,act_macro=logical_parser.last_defined_macro,act_combinator=logical_parser.last_defined_term))
 
        logical_parser.parse_code("(define OR (lambda (P:e=>t Q:e=>t x:e) (or (P x) (Q x))))")
        actions.append(SRAction(SRAction.COORD,act_macro=logical_parser.last_defined_macro,act_combinator=logical_parser.last_defined_term)) 

        return actions

    #transition system
    def init_configuration(self,input_size):
        """
        @param input_size : the input_size
        @return : a configuration
        """ 
        return ([],list(range(input_size)), 1.0)
        
    def shift(self,configuration,toklist,prefix_score):
        """
        Execs a shift action
        @param configuration: the input configuration
        @param toklist: the list of tokens
        @return configuration : the output configuration after shift
        """
        S,B,_ = configuration
        token = toklist[B[0]]
        stack_elt = StackElement(token.postag,B[0],token.logical_type)
        return (S + [stack_elt],B[1:],prefix_score)

    def drop(self,configuration,toklist,prefix_score):
        """
        Execs a shift and drop action.
        @param configuration: the input configuration
        @param toklist: the list of tokens
        @return configuration : the output configuration after shift
        """
        S,B,_ = configuration
        return (S,B[1:],prefix_score)
 
    def shift_unary(self,configuration,toklist,action,prefix_score):
        """
        Execs a shift and combinator (e.g. swap) action
        @param configuration: the input configuration
        @param toklist: the list of tokens
        @return configuration : the output configuration after shift
        """
        S,B,_ = configuration
        token = toklist[B[0]]
        stack_elt = StackElement(token.postag,B[0],action.logical_type(token.logical_type,None))
        return (S + [stack_elt],B[1:],prefix_score)

    def reduce_binary(self,configuration,toklist,action,prefix_score):
        """
        Execs a binary reduction
        @param configuration: the input configuration
        @param toklist: the list of tokens
        @param action : an SRAction instance
        @return configuration : the output configuration after reduction
        """
        S,B,_ = configuration
        stack_elt = StackElement(action.stack_label,action.head(S[-2].head_idx,S[-1].head_idx),action.logical_type(S[-2].logical_type,S[-1].logical_type))
        return (S[:-2]+[stack_elt],B,prefix_score)

    def reduce_coord(self,configuration,toklist,action,prefix_score): 
        """
        Execs a binary coord reduction, gobbling up the artificial token
        Args: 
           configuration (tuple): the input configuration
           toklist        (list): list of Token        
           action  (SRaction instance)
           prefix_score  (float): prefix score of a derivation.
        """
        S,B,_ = configuration
        stack_elt = StackElement(action.stack_label,action.head(S[-3].head_idx,S[-1].head_idx,S[-2].head_idx),action.logical_type(S[-3].logical_type,S[-1].logical_type))
        return (S[:-3]+[stack_elt],B,prefix_score) 
        
    def exec_action(self,configuration,toklist,action,prefix_score):
        """
        Executes an action on configuration and returns the output configuration.
        @param configuration: the input configuration
        @param toklist: the list of tokens
        @param action : an SRAction instance
        @param prefix_score: a float
        @return a configuration
        """
        if action.act_type == SRAction.SHIFT:
            return self.shift(configuration,toklist,prefix_score)
        elif action.act_type == SRAction.DROP:
            return self.drop(configuration,toklist,prefix_score)
        elif action.act_type == SRAction.SHIFT_UNARY:
            return self.shift_unary(configuration,toklist,action,prefix_score)
        elif action.act_type == SRAction.COORD:
            return self.reduce_coord(configuration,toklist,action,prefix_score)
        else:
            return self.reduce_binary(configuration,toklist,action,prefix_score)
    
    def generate_constraints(self,configuration,toklist,prev_action):
        """
        This generates a list of booleans: for each action, the boolean says if its prediction is allowed given the
        current configuration,toklist or not.
        @param configuration : a configuration
        @param toklist : the ordered list of tokens
        @param prev_action: the action that generated the current configuration
        @return a list of boolean flags
        """
        S,B,score = configuration
        
        flags = [True] * len(self.actions_list)
  
        for idx,act in enumerate(self.actions_list):
            #Structural constraints 
            if act.act_type in [SRAction.SHIFT,SRAction.DROP,SRAction.SHIFT_UNARY] and not B:
                flags[idx] = False
            elif act.act_type == SRAction.DROP and not prev_action is None and prev_action.act_type in [ SRAction.APPLY_LEFT,SRAction.APPLY_RIGHT ] :
                flags[idx] = False                
            elif act.act_type in [SRAction.SHIFT,SRAction.SHIFT_UNARY] and B:
                if toklist[B[0]].logical_form is None:
                    flags[idx] = False
                elif act.act_type == SRAction.SHIFT_UNARY and not toklist[B[0]].is_predicate():
                    flags[idx] = False
            elif len(S) < 2 and act.act_type in [ SRAction.APPLY_LEFT,SRAction.APPLY_RIGHT ]:
                flags[idx] = False
            elif act.act_type in [ SRAction.APPLY_LEFT, SRAction.APPLY_RIGHT ] and act.logical_type(S[-2].logical_type,S[-1].logical_type) == TypeSystem.FAILURE:
                #type constraints (binary case)
                flags[idx] = False
            elif act.act_type == SRAction.SHIFT_UNARY and act.logical_type(toklist[B[0]].logical_type) == TypeSystem.FAILURE:
                #type constraints (unary case)
                flags[idx] = False
            elif act.act_type == SRAction.COORD and (len(S) < 3 or S[-2].label not in ['OR','AND'] or act.logical_type(S[-3].logical_type,S[-1].logical_type) == TypeSystem.FAILURE):
                flags[idx] = False
            
        return flags    
    
    #scoring system (follows a CRF style scoring method)
    def extract_xrepresentation(self,configuration,toklist):
        """
        Extracts symbols from a configuration
        @param configuration : a configuration
        @param toklist : the ordered list of tokens
        @return a list of symbols (x values)
        """
        def normalize_list(bfr,N,defval='_'):
            bN = len(bfr)
            if bN == N :
                return bfr
            elif bN < N:       #padding (right)
                return bfr + [defval] * (N-bN)
            else:              #truncation
                return bfr[:N]

        S,B,score = configuration
        #print([ (s.label,toklist[s.head_idx].form) for s in S],B)
        if   len(S) >= 2:
            stack_labels  = [ ('S',S[0].label,S[1].label),('S',toklist[S[0].head_idx].form,toklist[S[1].head_idx].form)]
        elif len(S) == 1:
            stack_labels  = [ ('S',S[0].label,'#START#'),('S',toklist[S[0].head_idx].form,'#START#') ]
        elif len(S) == 0:
            stack_labels  = [ ('S','#START#') ]
            
        if len(B) >= 2:
            buffer_labels = [ ('B',toklist[B[0]].form,toklist[B[1]].form ) ] 
        elif len(B) == 1 : 
            buffer_labels = [ ('B',toklist[B[0]].form,"#END#") ]
        elif len(B) == 0 : 
            buffer_labels = [ ('B',"#END#") ]
       
        symlist = stack_labels + buffer_labels 
        return symlist

    def predict_actions(self,configuration,toklist,prev_action):
        """
        Provides a strictly positive score for each potential next action.
        Actions that are impossible get a 0 score.
        
        @param configuration : a configuration
        @param toklist : the ordered list of tokens
        @param prev_action: the action that generated this configuration
        @param return the scores for each action from this configuration
        """        
        def constrained_score(xvec,yaction,cflag):
            return exp(self.weights.dot(xvec_keys,yaction)) if cflag else 0
            
        xvec_keys = self.extract_xrepresentation(configuration,toklist)
        cflags    = self.generate_constraints(configuration,toklist,prev_action)
        
        return [ constrained_score(xvec_keys,act.stack_label,F) for (act,F) in zip(self.actions_list,cflags) ]

    def featurize_config_action(self,config,action,toklist,phi=None):
        """
        Extracts a feature vector for a configuration,SRAction couple
        @param configuration : a configuration
        @param action: a reference SRAction
        @param toklist : the ordered list of tokens
        @param phi: a SparseWeightVector to update
        @return a SparseWeightVector
        """
        symlist = self.extract_xrepresentation(config,toklist)
        if phi:
            phi += SparseWeightVector.code_phi(symlist,action.stack_label)
        else:
            phi = SparseWeightVector.code_phi(symlist,action.stack_label)
        return phi

    def featurize_derivation(self,derivation,toklist,phi=None):
        """
        Extracts a feature vector from a derivation
        @param derivation : a list of (configuration,SRAction) couples
        @param toklist : the ordered list of tokens
        @return a SparseWeightVector
        """
        if not phi:
            phi = SparseWeightVector( )
        for config,action in derivation:
            if action == None:
                return phi
            self.featurize_config_action(config,action,toklist,phi)            
        return phi

    #search & derivation
    def predict_beam(self,K,toklist):
        """
        Predicts derivations with beam search.
        @param K:       beam width
        @param toklist: a list of tokens
        @return a list of beams. Each beam is an ordered list of the configurations at time t
        and a boolean indicating parse success or failure.
        Note that the beam may return derivations whose type is not boolean.
        """
        def valid_final_config(config):
            S,B,score                = config
            return not B and len(S) == 1
        
        N          = len(toklist)
        next_beam  = [ BeamCell.init_element(self.init_configuration(N)) ]
        final_beam = [ ]
        while next_beam:
            this_beam = next_beam
            predictions = [ ] 
            for cell in this_beam:
                _ , prev_action , config = cell.prev, cell.action,cell.config 
                S,B,prefix                   = config  
                scores                       = self.predict_actions(config,toklist,prev_action)
                predictions.extend( [ (cell,act, score * prefix) for act,score in zip(self.actions_list,scores) if score > 0 ] ) 
            predictions.sort(key=lambda bcell : bcell[2], reverse = True) #sorts by scores
            predictions= predictions[:K]
            next_beam = [ ]
            for (prev_cell,act,score) in predictions: 
                config = self.exec_action(prev_cell.config,toklist,act,score)
                if valid_final_config(config):
                    final_beam.append( BeamCell(prev_cell,act,config)) 
                else:
                    next_beam.append( BeamCell(prev_cell,act,config))
        return final_beam

    
    def make_derivation(self,beam_cell):
        """
        This builds a derivation from a beam cell by backtracking to the origin.
        The last configuration is dropped (because always useless).
        @param beam_cell: the cell from where to start backtracking.
        @return a list of (configuration,SRAction) couples and its logical_type 
        """
        prev_cell,act,config = beam_cell.prev,beam_cell.action,beam_cell.config
        S,B,score = config
        
        dtype = S[-1].logical_type         #gets logical type 
        deriv      = [ (config,None)]      #might include a terminate action later on (more elegant)

        while act != None:
            deriv.append((prev_cell.config,act))
            beam_cell            = prev_cell
            prev_cell,act,config = beam_cell.prev,beam_cell.action,beam_cell.config
        deriv.reverse()

        return deriv,dtype
    
    def derivation2tree(self,derivation,toklist):
        """
        @param a derivation
        @return a ConsTree object
        """
        idx   = 0
        stack = [] 
        for config,action in derivation:
            if action == None:      #deriv is terminated
                break  
            elif action.act_type ==  SRAction.SHIFT:
                leaf = ConsTree(toklist[idx].form)
                stack.append(ConsTree(toklist[idx].logical_macro,children=[leaf]))        
                idx += 1
            elif action.act_type == SRAction.SHIFT_UNARY:
                leaf = ConsTree(toklist[idx].form)
                stack.append(ConsTree('%s[%s]'%(action.act_macro,toklist[idx].logical_macro),children=[leaf]))        
                idx += 1
            elif action.act_type == SRAction.DROP:
                idx += 1
            else:
                top    = stack.pop( )
                subtop = stack.pop( )
                stack.append(ConsTree(action.stack_label,children=[subtop,top]))
        return stack[-1]

    def make_query(self,derivation,toklist):
        """
        This builds a logical form (lambda term) from a derivation and returns the answer (if any)
        @param derivation : a parse derivation 
        @param toklist: a list of tokens
        @return a list of wikidata entities
        @TODO manage boolean (ASK) questions 
        """
        idx   = 0  
        stack = [ ]  
        for config,action in derivation:
            if action == None: 
                break  #deriv is terminated
            elif action.act_type == SRAction.SHIFT:
                lf = toklist[idx].logical_form.copy()
                stack.append( lf )
                idx += 1
            elif action.act_type == SRAction.DROP:
                idx += 1
            elif action.act_type == SRAction.SHIFT_UNARY:
                lf = toklist[idx].logical_form.copy()
                newtop = action.logical_apply(lf,None)
                stack.append(newtop)
                idx += 1
            else: 
                top    = stack.pop( )
                subtop = stack.pop( )
                newtop = action.logical_apply(subtop,top)
                stack.append(newtop)
                
        #TODO:that's hacked, find a more elegant solution (combined with ASK) later on
        query_term = stack[-1].value( ) 
        
        #print('query body',query_term.body) 
        results = query_term.ret_value(ret_type='SELECT',debug=False)
        #print('**',results,type(results),'**')
        entitylist = [ ]
        for assignment in results:
            if len(assignment) == 1: #factoid question, in principle we cannot have more than 1 var binding
                var,binding = assignment[0]
                entitylist.append(binding)
        return entitylist

    
    def best_answer(self,K,toklist):
        """
        Performs the  Q/A task and returns the set of answers computed from the best well typed parse tree
        @param K: beam size
        @param toklist: a list of tokens
        @return a list of entities (the answers)
        """
        all_beam,success = self.predict_beam(K,toklist)
        if not success:
            return [ ]
        for beam_cell in all_beam[-1]:
            deriv,dtype = self.make_derivation(all_beam,beam_cell)
            if len(dtype) == 1 and dtype[0] == 't':
                return self.make_query(deriv,toklist)
        return [ ]

    def eval_one(self,K,toklist,ref_values): 
        #like sgd train except it does eval.
        def is_correct(toklist,derivation,dtype,refset,success):
            """
            Assess the correctness of a question/answer couple.
            @param toklist : a list of tokens
            @param derivation : a derivation
            @param dtype : the type of the derivation
            @param refset : the set of correct answers to the question
            @param success :  a boolean indicating if the parse completed normally or got trapped early
            """ 
            if not derivation or not dtype or not success:
                return False
            #checks for type
            if not (len(dtype) == 1 and dtype[0] == 't'):
                return False
            sys.stdout.write('.')
            sys.stdout.flush()
            answer = self.make_query(derivation,toklist)
            for elt in answer:
                if elt in refset:
                    return True
            return False
        
        final_beam          = self.predict_beam(K,toklist)
        derivations_list    = [self.make_derivation(beam_cell) for beam_cell in final_beam]
        derivations_scores  = [d[-1][0][2] for d,dtype in derivations_list]
        Z                   = sum(derivations_scores)
        if Z == 0:
            raise ParseFailureError(len(derivations_list),Z,toklist)
        
        derivations_probs   = [ s / Z for s in derivations_scores ]
                
        #assess correct / incorrect results
        refset   = set(ref_values)
        cflags   = [is_correct(toklist,deriv,dtype,refset,len(final_beam) > 0) for deriv,dtype in derivations_list]

        for (deriv,dtype),flag,prob in sorted(zip(derivations_list,cflags,derivations_probs),key = lambda x: x[2] , reverse=True):
            return flag
        
        return False
        
    def sgd_train_one(self,K,toklist,ref_values,lr=0.1):
        """
        Performs an SGD update on a single example (uses a CRF style objective)
        @param K: beam size
        @param toklist: a list of tokens
        @param ref_values : a list of wikidata entities, the valid answers
        @param lr : learning rate
        @return the loglikelihood of this example
        """
        def is_correct(toklist,derivation,dtype,refset,success):
            """
            Assess the correctness of a question/answer couple.
            @param toklist : a list of tokens
            @param derivation : a derivation
            @param dtype : the type of the derivation
            @param refset : the set of correct answers to the question
            @param success :  a boolean indicating if the parse completed normally or got trapped early
            """ 
            if not derivation or not dtype or not success:
                return False
            #checks for type
            if not (len(dtype) == 1 and dtype[0] == 't'):
                return False
            sys.stdout.write('.')
            sys.stdout.flush()
            answer = self.make_query(derivation,toklist)
            for elt in answer:
                if elt in refset:
                    return True
            return False
        
        final_beam          = self.predict_beam(K,toklist)
        derivations_list    = [self.make_derivation(beam_cell) for beam_cell in final_beam]
        derivations_scores  = [d[-1][0][2] for d,dtype in derivations_list]
        Z                   = sum(derivations_scores)
        if Z == 0:
            raise ParseFailureError(len(derivations_list),Z,toklist)
        
        derivations_probs   = [ s / Z for s in derivations_scores ]
                
        #assess correct / incorrect results
        refset   = set([str(val) for val in ref_values])
        cflags   = [is_correct(toklist,deriv,dtype,refset,len(final_beam) > 0) for deriv,dtype in derivations_list]
        print('\n')
        #debug
        for (deriv,dtype),flag,prob in sorted(zip(derivations_list,cflags,derivations_probs),key = lambda x: x[2] , reverse=True):
            #print(','.join([str(action) for c,action in deriv]))
            if (len(dtype) == 1 and dtype[0] == 't'): #prints only well formed derivs
                print(self.derivation2tree(deriv,toklist),flag,prob)
                
        ncorrect = sum(cflags)
        
        #compute gradient
        grad     = SparseWeightVector()
        grad_neg = SparseWeightVector()
        LL = 0
        for (deriv,dtype),correct,dprob in zip(derivations_list,cflags,derivations_probs):
            if correct:
                phi = self.featurize_derivation(deriv,toklist)
                grad += phi
                LL   += log(dprob)
            else:
                phi = self.featurize_derivation(deriv,toklist)
                
            phi      *= (max(1,ncorrect) * dprob) #enforce (invalid) update even when no correct solution has been found.
            grad_neg += phi

        grad     -= grad_neg
        grad     *= lr
        
        #update
        self.weights += grad
        return LL 
 
    def train_model(self,data_filename,lr=0.1,epochs=50,beam_size=1):
        """
        Trains a model from a data file by stochastic gradient ascent.
        @param data_filename: the training set (json formatted, webquestion schema)
        @param lr : the learning rate
        """
        self.weights = SparseWeightVector()
        
        #read input data
        istream = open(data_filename)
        xylines = [line for line in istream]
        istream.close()
        
        #train model
        for e in range(epochs):
            LL = 0
            for xyline in xylines: 
                X,Y = self.lexer.tokenize_json(xyline,ref_answer=True)
                try:
                    LL += self.sgd_train_one(beam_size,X,Y,lr=lr)
                except ParseFailureError as p:
                    print(p)
                    print( )
            print('Epoch',e,'LogLikelihood =',LL) 

    def eval_songnan(self,data_filename,lr=0.1,epochs=50,beam_size=1):

        #read input data
        istream = open(data_filename)
        xylines = [line for line in istream]
        istream.close()

        corr      = 0
        N         = len(xylines)
        #train model
        for xyline in xylines:
            X,Y = self.lexer.tokenize_json(xyline,ref_answer=True)
            LL  = 0
            for e in range(epochs):
                try:
                    LL = self.sgd_train_one(beam_size,X,Y,lr=lr)
                except ParseFailureError as p:
                    print(p)
                    print( )
                print('Epoch',e,'LogLikelihood =',LL)
            try:
                res = self.eval_one(beam_size,X,Y)
            except ParseFailureError as p:
                corr = False
            corr += res
            print('\ncorrect' if corr else '\nincorrect')
        print('overall accurracy (#parse success)',corr/N)

                
if __name__ == '__main__': 

    #lex = DefaultLexer('strong-cpd.dic',entity_file='entities_dict.txt')
    lex = DefaultLexer('strong-cpd.dic',entity_file='dico_quan1.json')
    p = CCGParser(lex)
    #p.train_model('microquestions.json.txt',beam_size=500,lr=1.0,epochs=20)
    p.eval_songnan('microquestions.json',beam_size=500,lr=1.0,epochs=5)
    #p.train_model('sommeproba0.json',beam_size=500,lr=1.0,epochs=20)
    #p.train_model('devraitmarcher.json',beam_size=500,lr=1.0,epochs=20)
    
