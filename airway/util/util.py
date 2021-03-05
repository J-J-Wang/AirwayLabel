import sys
from pathlib import Path
import random
import string
from typing import List


def get_data_paths_from_args(outputs=1, inputs=1):
    """ Returns output and input data paths from sys.argv

    It exits if these are not defined
    """

    if len(sys.argv[1:]) < outputs+inputs:
        print("ERROR: Insufficient count of input/output paths supplied!")
        print(f"\tExpected {outputs} output paths and {inputs} input paths!")
        print(f"\tGot sys.argv: {sys.argv[1:]}")
        sys.exit(1)

    return (Path(sys.argv[index+1]) for index in range(outputs+inputs))
    # return (
    #     Path(arg) if index <= outputs+inputs else arg
    #     for index, arg in enumerate(sys.argv[1:], start=1)
    # )


def get_patient_name(patient_id):
    random.seed(patient_id)
    vowels = set("aeiou")
    consonants = set(string.ascii_lowercase) - vowels
    either = [sorted(consonants), sorted(vowels)]
    return "".join(random.choice(either[c % 2]) for c in range(4)).capitalize()


def get_keyword_to_patient_ids(stage_configs):
    for stage_config in stage_configs:
        print(stage_config)