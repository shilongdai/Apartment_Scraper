import json
import sys

import matplotlib.pyplot as plt
import seaborn as sns

import compile


def sorted_freq_list(items):
    items_freq = compile.freq_table(items)
    sorted_items = []
    for key, freq in items_freq.items():
        sorted_items.append((key, freq))
    sorted_items = sorted(sorted_items, key=lambda x: x[1])
    return sorted_items


if __name__ == "__main__":
    input_file = sys.argv[1]
    with open(input_file, "r") as input_fp:
        input_data = json.load(input_fp)
    amenities = []
    unique_features = []
    model_features = []
    for data in input_data:
        if "amenities" in data:
            amenities.extend(data["amenities"])
        if "models" in data:
            for model in data["models"]:
                if "features" in model:
                    model_features.extend(model["features"])
    sorted_amenities = sorted_freq_list(amenities)
    sorted_uniques = sorted_freq_list(model_features)
    sns.lineplot(x=range(len(sorted_amenities)), y=[x[1] for x in sorted_amenities])
    plt.show()
    sns.lineplot(x=range(len(sorted_uniques)), y=[x[1] for x in sorted_uniques])
    plt.show()

    selected_amenities = []
    for key, i in sorted_amenities:
        if i > 300:
            selected_amenities.append((key, i))
    selected_features = []
    for key, i in sorted_uniques:
        if i > 200:
            selected_features.append((key, i))
    print(selected_amenities)
    print(selected_features)
