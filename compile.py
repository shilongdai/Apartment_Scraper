import json
import math
import re
import statistics
import sys
from functools import partial

import pandas as pd

import extract

AMENITIES_LIMIT = 300
FEATURES_LIMIT = 200


def sorted_freq_list(items):
    items_freq = freq_table(items)
    sorted_items = []
    for key, freq in items_freq.items():
        sorted_items.append((key, freq))
    sorted_items = sorted(sorted_items, key=lambda x: x[1])
    return sorted_items


def parse_number_range(string):
    if "–" in string:
        strings = string.split("–")
    elif "-" in string:
        strings = string.split("-")
    else:
        strings = [string]
    numbers = []
    for string in strings:
        number = re.sub("[^0-9]+", "", string)
        if len(number) == 0:
            continue
        numbers.append(float(number))
    if len(numbers) == 0:
        return float("nan")
    return statistics.mean(numbers)


def freq_table(list_data):
    table = {}
    for item in list_data:
        if item not in table:
            table[item] = 1
        else:
            table[item] = table[item] + 1
    return table


def copy_header_address(raw, output):
    output["name"] = raw["name"]
    output["city"] = raw["city"]
    state_zip = raw["state_zip"].split(" ")
    output["state"] = state_zip[0]
    output["zip"] = int(state_zip[1])
    output["address"] = raw["address"]
    if "neighborhood" in raw:
        output["neighborhood"] = raw["neighborhood"]


def copy_desc_information(raw, output):
    if "custom_desc" not in raw:
        return
    desc = raw["custom_desc"]
    if "text" in desc:
        output["apartment_desc"] = desc["text"]
    if "unique_feature" in desc:
        output["unique_feature"] = desc["unique_feature"]
    if "amenities" in raw:
        output["amenities"] = raw["amenities"]
    if "neighborhood_desc" in raw:
        output["neighborhood_desc"] = raw["neighborhood_desc"]


def parse_fee_with_default(fee_str, default=0):
    fee = parse_number_range(fee_str)
    if math.isnan(fee):
        return default
    return fee


def summarize_pet_policies(pet_policy):
    one_time_fees = []
    rents = []
    deposits = []
    for policy in pet_policy:
        if "segments" not in policy:
            continue
        for segment in policy["segments"]:
            if segment["key"] == "One time Fee":
                one_time_fees.append(parse_fee_with_default(segment["content"]))
            if segment["key"] == "Monthly pet rent":
                rents.append(parse_fee_with_default(segment["content"]))
            if segment["key"] == "Pet deposit":
                deposits.append(parse_fee_with_default(segment["content"]))
    if len(one_time_fees) == 0:
        one_time_fees = [0]
    if len(rents) == 0:
        rents = [0]
    if len(deposits) == 0:
        deposits = [0]
    one_time_fee = statistics.median(one_time_fees)
    rent = statistics.median(rents)
    deposit = statistics.median(deposits)
    return {"one_time_fee": one_time_fee, "rent": rent, "deposit": deposit}


def compile_pet_info(fees, output):
    output["type"] = "unknown"
    if "Pet Policies (No Pets Allowed)" in fees:
        output["type"] = "disallowed"
    if "Pet Policies (Pets Negotiable)" in fees:
        output["type"] = "negotiable"
        output.update(summarize_pet_policies(fees["Pet Policies (Pets Negotiable)"]))
    if "Pet Policies" in fees:
        output["type"] = "allowed"
        output.update(summarize_pet_policies(fees["Pet Policies"]))


def extract_other_parking(garage, lot, street, covered, segment):
    cost = parse_fee_with_default(segment["content"])
    comment = ""
    if "comment" in segment:
        comment = "".join(segment["comment"]).lower()
    if "unassigned" in comment:
        lot.append(cost)
    if "indoor" in comment:
        covered.append(cost)
    if "assigned" in comment:
        lot.append(cost)
    if "garage" in comment:
        garage.append(cost)
    if "covered" in comment:
        covered.append(cost)
    if "uncovered" in comment:
        lot.append(cost)
    if "lot" in comment:
        lot.append(cost)
    if "outdoor" in comment:
        lot.append(cost)


def compile_parking_info(fees, output):
    garage_parking = []
    lot_parking = []
    street_parking = []
    covered_parking = []
    for parking_type in fees:
        if parking_type["name"] != "Parking":
            continue
        for segment in parking_type["segments"]:
            if segment["key"] == "Surface Lot":
                lot_parking.append(parse_fee_with_default(segment["content"]))
            if segment["key"] == "Street":
                street_parking.append(parse_fee_with_default(segment["content"]))
            if segment["key"] == "Garage":
                garage_parking.append(parse_fee_with_default(segment["content"]))
            if segment["key"] == "Covered":
                covered_parking.append(parse_fee_with_default(segment["content"]))
            if segment["key"] == "Other":
                extract_other_parking(garage_parking, lot_parking, street_parking, covered_parking, segment)
    if len(garage_parking) != 0:
        output["garage_fee"] = statistics.mean(garage_parking)
    if len(lot_parking) != 0:
        output["lot_fee"] = statistics.mean(lot_parking)
    if len(street_parking) != 0:
        output["street_fee"] = statistics.mean(street_parking)
    if len(covered_parking) != 0:
        output["covered_fee"] = statistics.mean(covered_parking)


def compile_fees_info(raw, output):
    if "fees" not in raw:
        return
    pet_info = {}
    compile_pet_info(raw["fees"], pet_info)
    parking_info = {}
    if "Fees" in raw["fees"]:
        compile_parking_info(raw["fees"]["Fees"], parking_info)
    if len(parking_info) > 0:
        output["parking"] = parking_info
    if len(pet_info) > 0:
        output["pet"] = pet_info


def extract_school_info(schools):
    result = []
    for school in schools:
        result.append({"name": school["name"], "type": school["type"], "zone": school["zone"]})
    return result


def compile_education_info(raw, output):
    if "education" not in raw:
        return
    education = raw["education"]
    college_infos = []
    if "colleges" in education:
        for college in education["colleges"]:
            name = college[0]
            distance = parse_number_range(college[-1])
            college_infos.append({"name": name, "distance": distance})
    school_infos = []
    if "public_schools" in education:
        school_infos.extend(extract_school_info(education["public_schools"]))
    if "private_schools" in education:
        school_infos.extend(extract_school_info(education["private_schools"]))
    if len(college_infos) > 0:
        output["colleges"] = college_infos
    if len(school_infos) > 0:
        output["schools"] = school_infos


def extract_transportation_section(transportation_list):
    results = []
    for transportation in transportation_list:
        name = transportation[0]
        distance = parse_number_range(transportation[-1])
        results.append({"name": name, "distance": distance})
    return results


def compile_transportation(raw, output):
    if "transportation" not in raw:
        return
    transportation = raw["transportation"]
    for t in transportation:
        t_type = t["type"]
        if t_type == "Transit / Subway":
            output["nearby_transit"] = extract_transportation_section(t["available"])
        if t_type == "Commuter Rail":
            output["nearby_rail"] = extract_transportation_section(t["available"])
        if t_type == "Airports":
            output["nearby_air"] = extract_transportation_section(t["available"])
        if t_type == "Shopping Centers":
            output["nearby_shopping"] = extract_transportation_section(t["available"])
        if t_type == "Parks and Recreation":
            output["nearby_rec"] = extract_transportation_section(t["available"])
        if t_type == "Military Bases":
            output["nearby_bases"] = extract_transportation_section(t["available"])


def copy_environment(raw, output):
    if "environment" not in raw:
        return
    environment = raw["environment"]
    if "transit_score" in environment:
        output["transit_score"] = parse_number_range(environment["transit_score"])
    if "bike_score" in environment:
        output["bike_score"] = parse_number_range(environment["bike_score"])
    if "walk_score" in environment:
        output["walk_score"] = parse_number_range(environment["walk_score"])
    if "sound_score" in environment:
        output["sound_score"] = parse_number_range(environment["sound_score"])
    if "traffic_level" in environment:
        output["traffic_level"] = environment["traffic_level"]
    if "busi_level" in environment:
        output["busi_level"] = environment["busi_level"]
    if "airport_level" in environment:
        output["airport_level"] = environment["airport_level"]


def find_model_median_area_rent(model):
    if "units" in model:
        unit_rents = []
        unit_sqfts = []
        for unit in model["units"]:
            unit_rents.append(parse_number_range(unit["rent"]))
            unit_sqfts.append(parse_number_range(unit["sqft"]))
        return statistics.median(unit_sqfts), statistics.median(unit_rents)
    else:
        rent = float("nan")
        if "rent" in model:
            rent = parse_number_range(model["rent"])
        sqft = parse_number_range(model["details"][2])
        return sqft, rent


def extract_model_setup(model, output):
    output["name"] = model["name"]
    if model["details"][0] == "Studio":
        output["beds"] = 0
    else:
        output["beds"] = parse_number_range(model["details"][0])
    output["baths"] = parse_number_range(model["details"][1])
    if "features" in model:
        output["features"] = model["features"]
    sqft, rent = find_model_median_area_rent(model)
    output["rent"] = rent
    output["sqft"] = sqft


def compile_model_information(raw, output):
    if "models" not in raw:
        return
    result = []
    for model in raw["models"]:
        model_output = {}
        extract_model_setup(model, model_output)
        if len(model_output) > 0:
            result.append(model_output)
    if len(result) > 0:
        output["models"] = result


def compile_information(raw, output):
    copy_header_address(raw, output)
    copy_desc_information(raw, output)
    compile_fees_info(raw, output)
    compile_education_info(raw, output)
    compile_transportation(raw, output)
    copy_environment(raw, output)
    compile_model_information(raw, output)


def convert_to_csv(output_data, processors):
    columns = {}
    handlers = []
    for processor in processors:
        cols, handler = processor()
        for col in cols:
            columns[col] = []
        handlers.append(handler)
    for data in output_data:
        if "models" not in data:
            continue
        for model in data["models"]:
            for handler in handlers:
                combined = handler(model, data)
                for col in combined:
                    columns[col].append(combined[col])
    return columns


def copy_apartment_processor(cols, default=None):
    def copy_handler(model, data):
        result = {}
        for col in cols:
            val = default
            if col in data:
                val = data[col]
            result[cols[col]] = val
        return result

    return set(cols.values()), copy_handler


def escape_for_csv(string):
    string = string.replace(" ", ".")
    string = re.sub("[^\\w.]+", "", string)
    while ".." in string:
        string = string.replace("..", ".")
    return string


def amenities_processor(compiled_data):
    amenities = []
    for data in compiled_data:
        if "amenities" in data:
            amenities.extend(data["amenities"])
    sorted_amenities = sorted_freq_list(amenities)
    cols = {}
    for key, freq in sorted_amenities:
        if freq >= AMENITIES_LIMIT:
            cols[key] = "amenities." + escape_for_csv(key)

    def handle_amenities(model, data):
        result = {}
        for target in cols.values():
            result[target] = False
        if "amenities" in data:
            for item in data["amenities"]:
                if item in cols:
                    result[cols[item]] = True
        return result

    return set(list(cols.values())), handle_amenities


def pet_processor():
    cols = {"pet.allowed", "pet.rent", "pet.deposit", "pet.fee"}

    def pet_handler(model, data):
        result = {"pet.allowed": None, "pet.rent": 0, "pet.deposit": 0, "pet.fee": 0}
        if "pet" in data:
            pet = data["pet"]
            if "type" in pet:
                result["pet.allowed"] = pet["type"]
            if "one_time_fee" in pet:
                result["pet.fee"] = pet["one_time_fee"]
            if "deposit" in pet:
                result["pet.deposit"] = pet["deposit"]
            if "rent" in pet:
                result["pet.rent"] = pet["rent"]
        return result

    return cols, pet_handler


def parking_processor():
    cols = {"has.lot", "has.garage", "has.street", "has.covered", "lot.fee", "garage.fee", "street.fee", "covered.fee",
            "lot.fee"}

    def parking_handler(model, data):
        result = {
            "has.lot": False,
            "has.garage": False,
            "has.street": False,
            "has.covered": False,
            "lot.fee": 0,
            "garage.fee": 0,
            "street.fee": 0,
            "covered.fee": 0
        }

        if "parking" in data:
            parking = data["parking"]
            if "garage_fee" in parking:
                result["has.garage"] = True
                result["garage.fee"] = parking["garage_fee"]
            if "lot_fee" in parking:
                result["has.lot"] = True
                result["lot.fee"] = parking["lot_fee"]
            if "street_fee" in parking:
                result["has.street"] = True
                result["street.fee"] = parking["street_fee"]
            if "covered_fee" in parking:
                result["has.covered"] = True
                result["covered.fee"] = parking["covered_fee"]
        return result

    return cols, parking_handler


def find_colleges_csv(compiled_data):
    college_vector_map = {}
    for data in compiled_data:
        if "colleges" in data:
            for college in data["colleges"]:
                college_vector_map[college["name"]] = escape_for_csv(college["name"])
    return college_vector_map


def college_aggregate_processor(college_vector_map):
    aggregate_cols = ["college.count"]

    def college_handler(model, data):
        result = {"college.count": 0}
        if "colleges" in data:
            for college in data["colleges"]:
                result["college.count"] += 1
        return result

    return aggregate_cols, college_handler


def college_name_processor(college_vector_map):

    def college_handler(model, data):
        result = {}
        for val in college_vector_map.values():
            result[val] = False
        if "colleges" in data:
            for college in data["colleges"]:
                result[college_vector_map[college["name"]]] = True
        return result

    return list(college_vector_map.values()), college_handler


def find_schools_csv(compiled_data):
    aggregate_cols = {}
    school_vector_map = {}
    for data in compiled_data:
        if "schools" in data:
            for school in data["schools"]:
                aggregate_cols[school["type"]] = escape_for_csv(school["type"])
                school_vector_map[school["name"]] = escape_for_csv(school["name"])
    return aggregate_cols, school_vector_map


def aggregate_school_processor(aggregate_cols):

    def school_handler(model, data):
        result = {}
        for val in aggregate_cols.values():
            result[val] = 0

        if "schools" in data:
            for school in data["schools"]:
                result[aggregate_cols[school["type"]]] += 1
        return result
    return set(aggregate_cols.values()), school_handler


def school_name_processor(school_vector_map):

    def school_handler(model, data):
        result = {}
        for val in school_vector_map.values():
            result[val] = False

        if "schools" in data:
            for school in data["schools"]:
                result[school_vector_map[school["name"]]] = True
        return result
    return set(school_vector_map.values()), school_handler


def transportation_processor():
    cols = {"transit.num", "rail.num", "air.num", "shopping.num", "rec.num", "base.num"}

    def transportation_handler(model, data):
        result = {
            "transit.num": 0,
            "rail.num": 0,
            "air.num": 0,
            "shopping.num": 0,
            "rec.num": 0,
            "base.num": 0
        }
        if "nearby_transit" in data:
            result["transit.num"] = len(data["nearby_transit"])
        if "nearby_rail" in data:
            result["rail.num"] = len(data["nearby_rail"])
        if "nearby_air" in data:
            result["air.num"] = len(data["nearby_air"])
        if "nearby_shopping" in data:
            result["shopping.num"] = len(data["nearby_shopping"])
        if "nearby_rec" in data:
            result["rec.num"] = len(data["nearby_rec"])
        if "nearby_bases" in data:
            result["base.num"] = len(data["nearby_bases"])
        return result

    return cols, transportation_handler


def copy_model_processor(cols, default=None):
    def copy_model_handler(model, data):
        result = {}
        for col in cols:
            val = default
            if col in model:
                val = model[col]
            result[cols[col]] = val
        return result

    return set(cols.values()), copy_model_handler


def features_processor(compiled_data):
    features = []
    for data in compiled_data:
        if "models" in data:
            for model in data["models"]:
                if "features" in model:
                    features.extend(model["features"])

    sorted_features = sorted_freq_list(features)
    cols = {}
    for key, freq in sorted_features:
        if freq >= FEATURES_LIMIT:
            cols[key] = "features." + escape_for_csv(key)

    def handle_features(model, data):
        result = {}
        for target in cols.values():
            result[target] = False
        if "features" in model:
            for item in model["features"]:
                if item in cols:
                    result[cols[item]] = True
        return result

    return set(list(cols.values())), handle_features


if __name__ == "__main__":
    extract_path = sys.argv[1]
    input_data = extract.load_json_from(extract_path)

    result = []
    for key in input_data:
        input_frame = input_data[key]
        output_frame = {}
        compile_information(input_frame, output_frame)
        if len(output_frame) > 0:
            result.append(output_frame)

    college_vector_map = find_colleges_csv(result)
    aggregate_schools, school_map = find_schools_csv(result)

    processors = [
        partial(copy_apartment_processor, {"name": "name", "city": "city", "state": "state",
                                           "zip": "zip", "address": "address"}),
        partial(copy_apartment_processor, {"neighborhood": "neighborhood"}, "Unknown"),
        pet_processor,
        parking_processor,
        partial(aggregate_school_processor, aggregate_schools),
        partial(college_aggregate_processor, college_vector_map),
        transportation_processor,
        partial(copy_apartment_processor, {"transit_score": "transit.score", "bike_score": "bike.score",
                                           "walk_score": "walk.score", "sound_score": "sound.score"}, float("nan")),
        partial(copy_apartment_processor, {"traffic_level": "traffic.level", "busi_level": "busi.level",
                                           "airport_level": "air.level"}, "Unknown"),
        partial(copy_model_processor, {"beds": "beds", "baths": "baths", "rent": "rent", "sqft": "sqft"}),
        partial(features_processor, result),
        partial(amenities_processor, result),
        partial(school_name_processor, school_map),
        partial(college_name_processor, college_vector_map)
    ]
    csv_dict = convert_to_csv(result, processors)
    dataframe = pd.DataFrame(csv_dict)
    with open("compile.json", "w") as output_file:
        json.dump(result, output_file)
    dataframe.to_csv("compile.csv")
