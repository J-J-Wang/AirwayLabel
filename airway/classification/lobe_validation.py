import re
from pathlib import Path
from typing import List

import networkx as nx
import yaml

from airway.util.config_parsers import parse_array_encoding
from airway.util.util import get_data_paths_from_args, get_ignored_patients

file_name = "data_quality_evaluation"


def get_input():
    output_data_path, tree_input_path = get_data_paths_from_args()
    config_path = Path("configs") / "classification.yaml"
    with open(config_path) as config_file:
        classification_config = yaml.load(config_file, yaml.FullLoader)
    trees: List[nx.Graph] = []
    for tree_path in Path(tree_input_path).glob('*/tree.graphml'):
        trees.append(nx.read_graphml(tree_path))
    return output_data_path, trees, classification_config


def main():
    output_path, trees, classification_config = get_input()
    ignored_patients = get_ignored_patients()
    encoding = {
        re.sub(r"^([RL])[a-z]+", r"\1", k): v
        for k, v in parse_array_encoding().items()
        if "Lobe" in k
    }
    decoding = dict(zip(encoding.values(), encoding.keys()))

    no_ignored = []
    with_ignored = []
    for index, tree in enumerate(trees, 1):
        for node_id in tree.nodes:
            node = tree.nodes[node_id]
            if node["split_classification"] in encoding:
                correctly_classified = node["lobe"] == encoding[node['split_classification']]
                if str(tree.graph['patient']) not in ignored_patients:
                    no_ignored.append(correctly_classified)
                    if not correctly_classified:
                        print(f"Patient {tree.graph['patient']}")
                        print(f"Mistaken {decoding[node['lobe']]} (Synapse) for {node['split_classification']}\n")
                with_ignored.append(correctly_classified)

    def show_stats(lis: List[bool]):
        s = sum(lis)
        t = len(lis)
        print(f"{s}/{t} = {s/t:%}")
    print("Without ignored patients:")
    show_stats(no_ignored)
    print("With ignored patients:")
    show_stats(with_ignored)


if __name__ == "__main__":
    main()