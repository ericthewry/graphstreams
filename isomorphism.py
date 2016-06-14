#! /usr/bin/python
import argparse
import cProfile
import mysql.connector
from getpass import getpass

from mapping import Mapping
from graph import DBGraph as Graph
from graph_gen import *
from sql_helpers import *




def generic_query_proc(query_graph,data_graph):
    iso_so_far = Mapping(directed = True)
    candidate_set = {}
    for e in query_graph.edges():
        candidate_set[e] = filter_candidates(query_graph, data_graph, e)
        if len(candidate_set[e]) == 0:
            print("No viable candidates for ", e)
            return False
    query_graph.edges(recalc = True)
    
    done = subgraph_search(iso_so_far, query_graph, data_graph, candidate_set,
                           0)
    print("Done searching!")
    return done

    
def subgraph_search(iso_so_far, query_graph, data_graph, candidate_set,
                    depth):

    if depth != iso_so_far.get_size():
        print("search depth:", depth, "should be equal to |ISO|", iso_so_far.get_size(),
              depth == iso_so_far.get_size())
    if depth >= query_graph.num_edges():
        print("Found a match!")
        return record(iso_so_far)
    
    else:
        e = query_graph.iterlist[depth]
        print("  "*depth,"Searching matches for:", e)
        candidates = refine_candidates(candidate_set[e], query_graph,
                                       data_graph, iso_so_far)
        
        for f in candidates:
            # print("  "*depth, e, "|--?-->", f, "\t?")
            if is_joinable(query_graph, data_graph, iso_so_far, e, f):
                if iso_so_far.insert(e,f):
                    subgraph_search(iso_so_far, query_graph, data_graph,
                                    candidate_set, depth + 1)
                    iso_so_far.remove(e,f)
                else:
                    next


                    
def is_joinable(query_graph, data_graph, iso_so_far, eid, fid):
    edge = query_graph.edge_tuple(eid)
    fdge = data_graph.edge_tuple(fid)

    return struct_sems(query_graph, data_graph, iso_so_far, edge, fdge)
    

## determines whether the addition of the pair edge-fdge to the mapping
## iso_so_far violates the structural conditions specified by query_graph.
## data_graph is the data graph,
def struct_sems(query_graph, data_graph, iso_so_far, edge, fdge):
    
    params = lambda x: (query_graph, data_graph, iso_so_far, edge, fdge, x)
    
    return _coincident_sems(*(params(True))) and \
           _coincident_sems(*(params(False)))
    

def _coincident_sems(query_graph, data_graph, iso_so_far, edge, fdge, pred):
    curr = 1 if pred else 2
    other = 2 if pred else 1
    ID = 0

    # select the appropriate functions
    coincident_in = query_graph.epred_in if pred else query_graph.esucc_in
    
    # for every coincident edge mapped by the iso
    for eeid in coincident_in(edge[curr], iso_so_far.domain()):
        # for every e in query_graph there is an f in data_graph
        ffid = iso_so_far.get(eeid[ID])
        # ensure there is a vertex v s.t. ( -f_pred->(v)-fdge->)
        if data_graph.edge_tuple(ffid)[other] != fdge[curr]:
            return False

    return True

    
def filter_candidates(query_graph, data_graph, e):
    return data_graph.edges()

def refine_candidates(candidates, query_graph, data_graph, iso_so_far):
    return candidates

def record(iso):
    print(iso)
    return True

def _label_match(e,f):
    return True


## The main function. Parses the command line arguments and sets up the
## computation as specified.
def main():
    
    parser = argparse.ArgumentParser(
        """A command-line interface for running 
        temporal graph isomorphism algorithms"""
        )

    # positional arguments
    parser.add_argument("database", help="The name of the database")
    
    parser.add_argument("query_table_name",
                        help="the name of the table of the query graph")

    parser.add_argument("data_table_name",
                        help="the table of the data graph to be queried")

    # optional flags
    parser.add_argument("-t", "--timer", action="store_true")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("-r", "--as-root", action="store_true")

    # graph generation parameters
    parser.add_argument("-q", "--make-query", type=int,
                        help="The number of edges for the query graph")
    
    parser.add_argument("-d", "--make-data", type=int,
                        help="The number pf edges for the data graph")
    
    parser.add_argument("-D", "--density", "--dens", type=float,
                        help="The desired density of the data graph")
                        
    parser.add_argument("-C", "--force-clear", action="store_true",
                        help="clear graph tables if they exist")
    
    parser.add_argument("--no-algo", dest="algo", action="store_false",
                        help="do not run any algorithms, only graph generation")
    
    args = parser.parse_args()

    print(args.database, args.query_table_name, args.data_table_name,
          args.timer, args.verbose, args.as_root, args.make_query,
          args.make_data, args.density, args.force_clear, args.algo)

    try:
        #get the password securely from the cli
        password = getpass()
        # if a password was supplied, or logging in as root
        # This forces the user have a password to log in as root.
        if len(password) > 0:
            if args.as_root:
                print("Logging in as root")
                db = mysql.connector.connect(user="root",
                                             db = args.database,
                                             passwd = password)
            else:
                db = mysql.connector.connect(db = args.database,
                                             passwd = password)
        else:
            print("No password given")
            db = mysql.connector.connect(db = args.database)
            
    except mysql.connector.Error as err:
        print("""Connecting to MySQL failed. If the problem persists check
                 password,
                 username, and
                 whether the database actually exists.""")
    else:

        # make the DATA graph
        make_graph(args.data_table_name, args.make_data, db, args.force_clear,
                   dens = args.density)

        # Make the query graph with default density
        make_graph(args.query_table_name, args.make_query, db, args.force_clear)

        # initalize the graph objects
        query_graph = Graph(args.query_table_name, db)
        data_graph = Graph(args.data_table_name, db)

        print("q has size", len(query_graph.edges()))
        print("G has size", len(data_graph.edges()))

        # find all patterns
        if args.algo:
            generic_query_proc(query_graph, data_graph)
            
        db.commit()
        db.close()
    return 0

if __name__ == "__main__": main()
