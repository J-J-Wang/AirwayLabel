""" This module does post processing after composing of the tree

# Function

This file is used to alter the tree generated by stage-05, which only
assembles it. This script removes any unnecessary nodes and recolors
nodes which are meant to be in a different lobe. Note that "recoloring"
stands for reassigning lobes in this script, since the lobes have their
preassigned colors in the visualizations and this script just "recolors"
them.

Node removal and recoloring have various methods, some of which are ran
until nothing changes in the graph. Node removal for example removes
nodes which have no children and have a distance of 
REMOVE_IF_GROUP_SIZE_LESS_THAN or less. Recoloring for example
recolors nodes if all their surrounding nodes are of a different
color. These are by far not all functionalities. Feel free to read
the method docstrings below.


# Constants:

REMOVE_IF_GROUP_SIZE_LESS_THAN: describes the number of groups below
which an edge will be merged with it's surrounding edges.

DIAMETER_TO_WEIGHT_RATIO: describes the ratio when an edge should
be collapsed due to it being thicker than it's length. Do not go
above 1.5, possibly only 1.0.

"""

import os
import math

import networkx as nx

from tree_extraction.compose_tree import set_attribute_to_node
from tree_extraction.compose_tree import set_level
from util.util import get_data_paths_from_args

# ============================================================================
# -------------------------------- Constants ---------------------------------
# ============================================================================

REMOVE_IF_GROUP_SIZE_LESS_THAN = 6
DIAMETER_TO_WEIGHT_RATIO = 0.85


# ============================================================================
# ---------------------- Mathematical Helping Functions ----------------------
# ============================================================================


def calc_diameter(area):
    return math.sqrt(4 * area / math.pi)


def distance(graph, node_a, node_b):
    """ Calculates Pythagorean distance between 2 points in graph
    """
    fr = graph.nodes[node_a]
    to = graph.nodes[node_b]
    return math.sqrt(
        (fr["x"] - to["x"]) ** 2
        + (fr["y"] - to["y"]) ** 2
        + (fr["z"] - to["z"]) ** 2
    )


# ============================================================================
# ------------------------ NetworkX Helping Functions ------------------------
# ============================================================================


def load_graph(path):
    """ Loads graph from given path
    """
    return nx.read_graphml(path)


def remove_nodes(graph, nodes_to_be_removed):
    """ Removes given nodes from graph
    """
    nodes_removed = len(nodes_to_be_removed)
    nodes_before = nx.number_of_nodes(graph)
    nodes_remaining = nodes_before - nodes_removed
    for node in nodes_to_be_removed:
        graph.remove_node(node)
    print(f"Removed {nodes_removed} nodes ({nodes_before} -> {nodes_remaining}))")


def combine_group_sizes(graph, node_pre, node, node_suc):
    """ Combines 2 group size strings of 2 edges into one and returns it
    """
    e1 = graph[node_pre][node]
    e2 = graph[node][node_suc]
    return e1["group_sizes"] + " " + e2["group_sizes"]


def merge_edges(graph, predecessor, node, successor):
    """ Correctly merges 2 edges
    """
    graph.add_edge(
        predecessor,
        successor,
        weight=distance(graph, predecessor, successor),
        group_sizes=combine_group_sizes(graph, predecessor, node, successor),
    )


def assign_children_count(graph):
    """ Assigns each node a number which specifies how many children it has
    """

    successors = dict(nx.bfs_successors(graph, "0"))
    all_successors = {}

    def successor_count(curr_node='0'):
        if curr_node in successors:
            count = sum([successor_count(succ) for succ in successors[curr_node]])
        else:
            count = 0
        all_successors[curr_node] = count
        return count + 1

    successor_count()
    for node, count in all_successors.items():
        graph.nodes[node]["successor_count"] = count


def get_successor_lobes(graph, return_count=False):
    """ Returns a dict with each node and a set with all it's successors lobes
    """

    successors = dict(nx.bfs_successors(graph, "0"))
    all_successors = {}

    def successor_lobes(curr_node='0'):
        lobes = {}
        if curr_node in successors:
            for succ in successors[curr_node]:
                for key, occ in successor_lobes(succ).items():
                    lobes[key] = lobes.get(key, 0) + occ
        all_successors[curr_node] = lobes
        curr_lobe = graph.nodes[curr_node]['lobe']
        if curr_lobe != 0:
            lobes[curr_lobe] = lobes.get(curr_lobe, 0) + 1
        return lobes

    successor_lobes()
    if return_count:
        return all_successors
    else:
        return {lobe: set(occ.keys()) for lobe, occ in all_successors.items()}


def set_attribute_recursively(graph, node, attribute_name, value):
    """ Traverses the tree from the root node and starting at `node`
    sets all `attribute_name` to `value`
    """
    successors = dict(nx.bfs_successors(graph, '0'))

    def rec_traverse(curr_node):
        graph.nodes[curr_node][attribute_name] = value
        if curr_node in successors:
            for succ in successors[curr_node]:
                rec_traverse(succ)

    rec_traverse(node)


# ============================================================================
# --------------- Functions for Removing Nodes from the Graph ----------------
# ============================================================================


def remove_minor_edges(graph):
    """ Removes edges which have no children and are very short (see constant)
    """
    has_successors = {s[0] for s in nx.bfs_successors(graph, "0")}
    nodes_to_be_removed = []
    for fr, to in nx.bfs_edges(graph, "0"):
        if to not in has_successors:

            # Alternative way of checking, compares the current diameter with edge length
            # node_diameter = calc_diameter(graph.nodes.data()[fr]['group_size'])
            # avg_edge_length = graph[fr][to]['group_sizes'].count(' ')
            # if avg_edge_length - node_diameter < REMOVE_IF_GROUP_SIZE_LESS_THAN:
            if graph[fr][to]['group_sizes'].count(' ') < REMOVE_IF_GROUP_SIZE_LESS_THAN:
                nodes_to_be_removed.append(to)
    remove_nodes(graph, nodes_to_be_removed)


def straighten_edges(graph):
    """ Merges all nodes which only have 1 child with their parent
    """
    predecessors = dict(nx.bfs_predecessors(graph, "0"))
    only_single_successor = [
        (n, *s) for n, s in nx.bfs_successors(graph, "0") if len(s) == 1
    ]
    nodes_to_be_removed = []
    cant_be_removed = {"0"}
    for node, successor in only_single_successor:
        if node not in cant_be_removed:
            predecessor = predecessors[node]
            nodes_to_be_removed.append(node)
            merge_edges(graph, predecessor, node, successor)
            cant_be_removed.add(successor)
    remove_nodes(graph, nodes_to_be_removed)


def merge_close_nodes(graph):
    """ Merges nodes when they are really close to each other
    """
    has_successors = dict(nx.bfs_successors(graph, "0"))
    nodes_to_be_removed = []
    edges_to_be_merged = []
    cant_be_removed = {"0"}
    for predecessor, node in nx.bfs_edges(graph, "0"):
        if node not in cant_be_removed:
            curr = graph[predecessor][node]
            nums = list(map(int, curr["group_sizes"].split()))
            weight = curr['weight']
            diameter = calc_diameter(sum(nums) / len(nums))
            if weight < diameter * DIAMETER_TO_WEIGHT_RATIO:
                if node in has_successors:
                    for successor in has_successors[node]:
                        cant_be_removed.add(successor)
                        edges_to_be_merged.append((graph, predecessor, node, successor))
                nodes_to_be_removed.append(node)
                print(f"Merging: weight: {weight:.2f}, average: {diameter:.2f}", end=' -> ')
                print(curr)
    for edge_merge in edges_to_be_merged:
        merge_edges(*edge_merge)
    remove_nodes(graph, nodes_to_be_removed)


def remove_children_without_children(graph):
    """ Remove all nodes which don't have any children in the first 4 layers
    """
    successors = dict(nx.bfs_successors(graph, '0'))
    nodes_to_check = set('0')
    for _ in range(3):
        new_nodes = set()
        for node in nodes_to_check:
            if node in successors:
                for succ in successors[node]:
                    new_nodes.add(succ)
        # Unify sets
        nodes_to_check |= new_nodes

    nodes_to_be_removed = []

    for adj in nodes_to_check:
        if adj not in successors:
            nodes_to_be_removed.append(adj)

    if nodes_to_be_removed:
        print(f"Found {len(nodes_to_be_removed)} in top 3 layers to remove")
    remove_nodes(graph, nodes_to_be_removed)


# ============================================================================
# -------------------------------- Recoloring --------------------------------
# ============================================================================

def recolor_if_all_adjacent_have_different_color(graph):
    """ Iterates over each node and recolors if _all_ adjacent nodes have a
    different color
    """
    root_successors = get_successor_lobes(graph, return_count=True)['0']
    for node in graph.nodes():
        n = graph.nodes
        if n[node]['lobe'] != 0:
            adjacent_lobes = {
                n[adj]['lobe'] for adj in graph[node] if n[adj]['lobe'] != 0
            }
            if len(adjacent_lobes) == 1:
                surrounding_lobe = list(adjacent_lobes)[0]
                if surrounding_lobe != n[node]['lobe']:
                    if root_successors[n[node]['lobe']] > 1:
                        print(f"Recoloring node {node} from {n[node]['lobe']} to {surrounding_lobe}")
                        n[node]['lobe'] = surrounding_lobe
                        root_successors[n[node]['lobe']] -= 1
                        root_successors[surrounding_lobe] += 1


def possibly_make_neutral_above_level_4(graph):
    """ Recolors the highest node which only has right middle lobe
    and right lower lobe nodes below it
    """
    for node, successor_lobes in get_successor_lobes(graph).items():
        if graph.nodes[node]['level'] <= 4 and graph.nodes[node]['lobe'] != 0:
            if len(successor_lobes) > 1:
                print(f"Making node {node} neutral since it's successors are: {successor_lobes}")
                graph.nodes[node]['lobe'] = 0
        # if 4 in successor_lobes and 5 in successor_lobes:
        # print(node, successor_lobes)


def recolor_if_successors_all_different_color(graph):
    """ Iterates over each node and recolor a node of all it's successors
    have a different color
    """
    for node, successor_lobes in get_successor_lobes(graph).items():
        curr_lobe = graph.nodes[node]['lobe']
        if curr_lobe != 0:
            if len(successor_lobes) == 1 and curr_lobe not in successor_lobes:
                c = list(successor_lobes)[0]
                graph.nodes[node]['lobe'] = c
                print(f"Recoloring node {node} from {curr_lobe} to {c}")


def add_new_parent_for_lobe(graph):
    """ Recolors a neutral node if it would connect several subtrees of the same color
    """
    successors = dict(nx.bfs_successors(graph, '0'))
    for node in graph.nodes():
        curr_lobe = graph.nodes[node]['lobe']
        if curr_lobe == 0:
            if node in successors:
                lobes = [graph.nodes[succ]['lobe'] for succ in successors[node]]
                occ = {lobe: lobes.count(lobe) for lobe in lobes}
                new_lobe = [
                    lobe for lobe, count in occ.items()
                    if 1 < count == max(occ.values())
                ]
                if new_lobe:
                    if new_lobe[0] != curr_lobe:
                        graph.nodes[node]['lobe'] = new_lobe[0]
                        print(f"Adding new parent node {node} from {curr_lobe} to {new_lobe[0]}")


def recolor_entire_subtree_to_majority_at_level_4_or_5(graph):
    """ Very drastic measure, recolors subtree at depth at 4 or 5 to the majority
    of its successors. Note that level 5 will be used instead of 4 if its successors
    are of type 4 or 5 (right middle lobe and right upper lobe)
    """
    all_successor_lobes = get_successor_lobes(graph, return_count=True)
    root_successors = all_successor_lobes['0']
    print(root_successors)
    for node, successor_lobes in all_successor_lobes.items():
        if 1 < len(successor_lobes):
            n = graph.nodes[node]

            # Add exception for the case of lobes 4, 5
            exc = [lobe_type in successor_lobes for lobe_type in [4, 5]]

            # This if checks whether the current node is on level 4,
            # or if it is on level 5 if below it are only lobe of type 4 and 5
            if (n['level'] == 4 and not any(exc)) or (n['level'] == 5 and all(exc)):
                print(successor_lobes)
                new_lobe_max = max(successor_lobes, key=lambda key: successor_lobes[key])

                # In case there is more than one with the same count try all of them
                possible_new_lobes = [
                    lobe for lobe, _ in sorted(successor_lobes.items(), key=lambda x: x[1], reverse=True)
                ]
                # print(possible_new_lobes)

                # If none of the lobes gets entirely removed then proceed
                for new_lobe in possible_new_lobes:
                    difference_per_lobe_root_and_curr_node = [
                        count - successor_lobes.get(lobe, 0)
                        for lobe, count in root_successors.items()
                        if lobe != new_lobe
                    ]
                    # print(difference_per_lobe_root_and_curr_node)
                    if all(difference_per_lobe_root_and_curr_node):
                        set_attribute_recursively(graph, node, 'lobe', new_lobe)
                        print(f"Reassigning all nodes below {node} to {new_lobe}")
                        break


# ============================================================================
# ----------------------------------- Main -----------------------------------
# ============================================================================


def main():
    """ Executes all methods given above in the correct order
    """
    # |>-<-><-><-><-><-><-><-<|
    # |>- Process arguments -<|
    # |>-<-><-><-><-><-><-><-<|

    output_data_path, input_data_path = get_data_paths_from_args()

    # |>-<-><-><-><->-<|
    # |>- Load graph -<|
    # |>-<-><-><-><->-<|

    graph = load_graph(input_data_path / "tree.graphml")

    assert nx.is_tree(graph), "ERROR: Graph is not a tree!"

    # |>-><-><-><-><-><-<|
    # |>- Process tree -<|
    # |>-><-><-><-><-><-<|

    print(f"===== Node Removal =====")

    # Run each of these multiple times since they do something on each
    # iteration. Quit when nothing changes
    iteration = 0
    while True:
        node_count = graph.number_of_nodes()
        print(f"=== Iteration {iteration} ===")

        remove_minor_edges(graph)
        straighten_edges(graph)
        merge_close_nodes(graph)
        remove_children_without_children(graph)

        iteration += 1
        if node_count == graph.number_of_nodes():
            break

    # |>--><-><-><-><-><-><-><-><-><-><-><-><-><--<|
    # |>- Reset attributes from the other script -<|
    # |>--><-><-><-><-><-><-><-><-><-><-><-><-><--<|

    assign_children_count(graph)

    graph = set_level(graph)
    graph = set_attribute_to_node(graph, ('level', 2), ('lobe', 0))
    graph = set_attribute_to_node(graph, ('level', 3), ('lobe', 0))

    assert nx.is_tree(graph), "ERROR: Graph is no longer a tree!"

    # |>-<-><-><-><-><-><-><-><->-<|
    # |>- Write pre-colored tree -<|
    # |>-<-><-><-><-><-><-><-><->-<|

    print(f"===== Recoloring =====")

    if not output_data_path.exists():
        output_data_path.mkdir(parents=True, exist_ok=True)

    nx.write_graphml(graph, output_data_path / "pre-recoloring.graphml")

    # |>-<-><-><-><->-<|
    # |>- Recoloring -<|
    # |>-<-><-><-><->-<|

    for _ in range(5):
        recolor_if_all_adjacent_have_different_color(graph)
        recolor_if_successors_all_different_color(graph)

    recolor_entire_subtree_to_majority_at_level_4_or_5(graph)
    possibly_make_neutral_above_level_4(graph)
    add_new_parent_for_lobe(graph)

    # |>-<-><-><-><->-<|
    # |>- Write tree -<|
    # |>-<-><-><-><->-<|

    nx.write_graphml(graph, output_data_path / "tree.graphml")


if __name__ == "__main__":
    main()
