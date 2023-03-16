import json
import multiprocessing as mp
import os
import re
import sys

import bs4

import scrape

PROCESS_COUNT = 11

config_file = scrape.config_file
PROPERTY_HEADER_SECTION_SELECTOR = "div.profilePropertyInfoWrapper#propertyHeader"
PROPERTY_NAME_SELECTOR = "h1#propertyName"
PROPERTY_ADDRESS_SECTION_SELECTOR = "div.propertyAddressContainer"
ADDRESS_PART_SELECTOR = "h2 span"
BREAD_SELECTOR = "div[id='breadcrumbs-container']"
CRUMB_SELECTOR = "span[class='crumb']"

DESC_SECTION_SELECTOR = "section#descriptionSection"
CUSTOM_DESC_SELECTOR = "p"
UNIQUE_FEATURE_SELECTOR = "div#uniqueFeatures"
UNIQUE_LIST_ITEM_SELECTOR = "ul li span"

AMENITIES_SELECTOR = "section#amenitiesSection"
AMENITIES_CARD_SELECTOR = "div.amenityCard"
AMENITIES_LABEL_SELECTOR = "p.amenityLabel"
AMENITIES_LIST_SELECTOR = "ul li span"

FEE_SECTION_SELECTOR = "section#feesSection > div"
FEE_TITLES_SELECTOR = "h3.feePolicyTitle"
FEE_SECTION_NOTE_SELECTOR = "div.clampWrapper"
FEE_SECTION_HEADER_SELECTOR = "h4.header-column"
FEE_SECTION_NOTE_LABEL_SELECTOR = "span"
FEE_SECTION_LIST_SELECTOR = "ul li"
FEE_SECTION_LIST_ROW_SELECTOR = "div.component-row"

NEIGHBOR_SECTION_SELECTOR = "section#subMarketSection"
NEIGHBOR_TEXT_SELECTOR = "div.overViewWrapper"

EDUC_SECTION_SELECTOR = "div#educationContainer"
EDUC_COLLEGE_SELECTOR = "div#profilev2College"

SCHOOL_SECTION_SELECTOR = "div#profilev2SchoolsModule"
PUBLIC_SCHOOL_SECTION_SELECTOR = "div.schoolsPublicContainer"
PRIVATE_SCHOOL_SECTION_SELECTOR = "div.schoolsPrivateContainer"
SCHOOL_CARD_SELECTOR = "div.card"
SCHOOL_CARD_NAME_SELECTOR = "div.title"
SCHOOL_CARD_TYPE_SELECTOR = "div.subtitle"
SCHOOL_CARD_ATTR_SELECTOR = "div.bodyTextLine"
SCHOOL_CARD_ZONE_SELECTOR = "div.nearbySchools span"

TRANSPORTATION_HEAD_SELECTOR = "thead.longLabel th.headerCol1"
TRANSPORTATION_DETAIL_SECTION_SELECTOR = "div.transportationDetail"
TRANSPORTATION_SECTION_SELECTOR = "section#transportationSection"
TRANSPORTATION_SELECTOR = "div.transportationDetail table tbody"
WALK_SCORE_SELECTOR = "div#transportationScoreCard > div.walkScore div.score"
TRANSIT_SCORE_SELECTOR = "div#transportationScoreCard > div.transitScore div.score"
BIKE_SCORE_SELECTOR = "div#transportationScoreCard > div.bikeScore div.score"
SOUND_SCORE_SECTION_SELECTOR = "div#soundScoreSection"
SOUND_SCORE_SELECTOR = "div.score"
TRAFFIC_LEVEL_SELECTOR = "div.soundScoreCategory span.ssTrafficData"
AIRPORT_LEVEL_SELECTOR = "div.soundScoreCategory span.ssAirportsData"
BUSI_LEVEL_SELECTOR = "div.soundScoreCategory span.ssBusinessData"

PRICE_SECTION_SELECTOR = "div#pricingView"
PRICE_MODEL_SELECTOR = "div.pricingGridItem"
PRICE_MODEL_OVERVIEW_SELECTOR = "div.priceBedRangeInfo"
MODEL_NAME_SELECTOR = "span.modelName"
MODEL_RENT_SELECTOR = "span.rentLabel"
MODEL_DETAILS_SELECTOR = "h4.detailsLabel span.detailsTextWrapper > span"
MODEL_FEATURES_SELECTOR = "ul.allAmenities li ul li"
MODEL_UNITS_SELECTOR = "li.unitContainer"
MODEL_UNITS_SQFT_SELECTOR = "div.sqftColumn span:nth-child(2)"
MODEL_UNITS_RENT_SELECTOR = "div.pricingColumn span:nth-child(2)"

TOP_MODEL_SELECTOR = "ul[class='priceBedRangeInfo']"
TOP_INFO_SEGMENT_SELECTOR = "div[class='priceBedRangeInfoInnerContainer']"
TOP_INFO_NAME_SELECTOR = "p[class='rentInfoLabel']"
TOP_INFO_CONTENT_SELECTOR = "p[class='rentInfoDetail']"

STATE_ZIP_REGEX = "stateZipContainer"
NEIGHBOR_REGEX = "neighborhoodAddress"
ADDRESS_REGEX = "delivery-address"


def extract_address_part(index, part, output_data):
    if "class" not in part.attrs:
        return
    if re.match(STATE_ZIP_REGEX, part.attrs["class"][0]):
        output_data["state_zip"] = part.get_text().strip().replace("\n", " ")
        return
    if re.match(NEIGHBOR_REGEX, part.attrs["class"][0]):
        output_data["neighborhood"] = part.get_text().strip()[2:]
        return
    if re.match(ADDRESS_REGEX, part.attrs["class"][0]):
        output_data["address"] = part.get_text()
        return


def extract_header(soup, output_data):
    header_section = soup.select_one(PROPERTY_HEADER_SECTION_SELECTOR)
    bread_section = header_section.select_one(BREAD_SELECTOR)
    crumbs = bread_section.select(CRUMB_SELECTOR)
    address_section = header_section.select_one(PROPERTY_ADDRESS_SECTION_SELECTOR)
    address_parts = address_section.select(ADDRESS_PART_SELECTOR)
    for i, part in enumerate(address_parts):
        extract_address_part(i, part, output_data)
    property_name = soup.select_one(PROPERTY_NAME_SELECTOR)
    output_data["name"] = property_name.get_text().strip()
    output_data["type"] = crumbs[0].text.strip()
    output_data["city"] = crumbs[2].text.strip()


def extract_apartment_desc(soup, output_data):
    output_data["custom_desc"] = {}
    desc_section = soup.select_one(DESC_SECTION_SELECTOR)
    if desc_section is None:
        return
    custom_desc = desc_section.select_one(CUSTOM_DESC_SELECTOR)
    if custom_desc is not None and len(custom_desc.attrs) == 0:
        output_data["custom_desc"]["text"] = custom_desc.get_text()

    unique_section = soup.select_one(UNIQUE_FEATURE_SELECTOR)
    items = []
    if unique_section is not None:
        unique_list = unique_section.select(UNIQUE_LIST_ITEM_SELECTOR)
        for item in unique_list:
            items.append(item.get_text().strip())
        items = list(set(items))
        output_data["custom_desc"]["unique_feature"] = items


def extract_amenities_cards(soup):
    cards = soup.select(AMENITIES_CARD_SELECTOR)
    result = []
    for card in cards:
        label = card.select_one(AMENITIES_LABEL_SELECTOR)
        if label is not None:
            result.append(label.get_text().strip())
    return result


def extract_amenities_lists(soup):
    list_items = soup.select(AMENITIES_LIST_SELECTOR)
    result = []
    for item in list_items:
        result.append(item.get_text().strip())
    return result


def extract_amenities(soup, output_data):
    amenities_section = soup.select_one(AMENITIES_SELECTOR)
    if amenities_section is None:
        return
    result = []
    result.extend(extract_amenities_cards(amenities_section))
    result.extend(extract_amenities_lists(amenities_section))
    output_data["amenities"] = list(set(result))


def clean_for_json_attr(string):
    subbed = string.strip().replace(" ", "_")
    subbed = re.sub("[\\W]+", "", subbed)
    return subbed.lower()


def extract_fee_section_note(soup, content_list):
    note_section = soup.select_one(FEE_SECTION_NOTE_SELECTOR)
    if note_section is not None:
        note_label = note_section.select_one(FEE_SECTION_NOTE_LABEL_SELECTOR)
        note_label_text = "note"
        if note_label is not None:
            note_label_text = note_label.get_text().strip()
        note_content_text = note_section.find(string=True, recursive=False).text.strip()
        content_list.append({"key": note_label_text, "content": note_content_text})


def extract_fee_section_table(soup, content_list):
    section_list = soup.select(FEE_SECTION_LIST_SELECTOR)
    for item in section_list:
        row_elements = list(item.select(FEE_SECTION_LIST_ROW_SELECTOR))
        if len(row_elements) == 0:
            continue
        key_pair = list(row_elements[0].findChildren("div", recursive=False))
        key = key_pair[0].get_text().strip()
        content = key_pair[1].get_text().strip()
        comments = []
        for i in range(1, len(row_elements)):
            comments.append(row_elements[i].get_text().strip())
        segment = {"key": key, "content": content}
        if len(comments) != 0:
            segment["comment"] = comments
        content_list.append(segment)


def extract_fee_section(soup, output_list):
    header_col = soup.select_one(FEE_SECTION_HEADER_SELECTOR)
    if header_col is None:
        return
    name = header_col.get_text().strip()
    section_data = {"name": name}

    data_content = []
    extract_fee_section_note(soup, data_content)
    extract_fee_section_table(soup, data_content)

    if len(data_content) != 0:
        section_data["segments"] = data_content
        output_list.append(section_data)


def extract_fees(soup, output_data):
    fee_section = soup.select_one(FEE_SECTION_SELECTOR)
    if fee_section is None:
        return
    output_data["fees"] = {}
    fee_policy_titles = fee_section.select(FEE_TITLES_SELECTOR)
    for title in fee_policy_titles:
        title_attr = title.get_text().strip()
        output_data["fees"][title_attr] = []
        next_sibling = title.find_next_sibling()
        if next_sibling is None:
            continue
        while next_sibling is not None and next_sibling.name == "div":
            extract_fee_section(next_sibling, output_data["fees"][title_attr])
            next_sibling = next_sibling.find_next_sibling()


def extract_neighbor_desc(soup, output_data):
    neighbor_section = soup.select_one(NEIGHBOR_SECTION_SELECTOR)
    if neighbor_section is not None:
        neighbor_text_section = neighbor_section.select_one(NEIGHBOR_TEXT_SELECTOR)
        neighbor_section_text = neighbor_text_section.get_text().strip()
        output_data["neighborhood_desc"] = neighbor_section_text


def extract_transportation(soup):
    transportation_section = soup.select_one(TRANSPORTATION_SELECTOR)
    if transportation_section is None:
        return []
    transportation_infos = transportation_section.select("tr")
    result = []
    for row in transportation_infos:
        row_list = []
        for col in row.select("td"):
            row_list.append(col.get_text().strip())
        result.append(row_list)
    return result


def extract_colleges(soup, output_data):
    college_section = soup.select_one(EDUC_COLLEGE_SELECTOR)
    if college_section is None:
        return
    college_transportation = extract_transportation(college_section)
    if len(college_transportation) != 0:
        output_data["colleges"] = college_transportation


def extract_school_info(soup):
    school_cards = soup.select(SCHOOL_CARD_SELECTOR)
    result = []
    for card in school_cards:
        name_elt = card.select_one(SCHOOL_CARD_NAME_SELECTOR)
        type_elt = card.select_one(SCHOOL_CARD_TYPE_SELECTOR)
        zone_elt = card.select_one(SCHOOL_CARD_ZONE_SELECTOR)
        attribute_elts = card.select(SCHOOL_CARD_ATTR_SELECTOR)
        attributes = []
        for attr in attribute_elts:
            attributes.append(attr.get_text().strip())
        card_data = {"name": name_elt.get_text().strip(), "type": type_elt.get_text().strip(),
                     "zone": zone_elt.get_text().strip()}
        if len(attributes) > 0:
            card_data["attributes"] = attributes
        result.append(card_data)
    return result


def extract_schools(soup, output_data):
    public_school_section = soup.select_one(PUBLIC_SCHOOL_SECTION_SELECTOR)
    if public_school_section is not None:
        public_schools = extract_school_info(public_school_section)
        if len(public_schools) > 0:
            output_data["public_schools"] = public_schools
    private_school_section = soup.select_one(PRIVATE_SCHOOL_SECTION_SELECTOR)
    if private_school_section is not None:
        private_schools = extract_school_info(private_school_section)
        if len(private_schools) > 0:
            output_data["private_schools"] = private_schools


def extract_education(soup, output_data):
    education_section = soup.select_one(EDUC_SECTION_SELECTOR)
    if education_section is None:
        return
    education_data = {}
    extract_colleges(soup, education_data)
    extract_schools(soup, education_data)
    if len(education_data) > 0:
        output_data["education"] = education_data


def extract_transportation_details(soup):
    transportation_head = soup.select_one(TRANSPORTATION_HEAD_SELECTOR)
    if transportation_head is None:
        return None
    head_text = transportation_head.get_text().strip()
    transportation_list = extract_transportation(soup)
    if len(transportation_list) > 0:
        return {"type": head_text, "available": transportation_list}


def extract_nearby_transportation(soup, output_data):
    transportation_section = soup.select_one(TRANSPORTATION_SECTION_SELECTOR)
    if transportation_section is None:
        return
    transportation_details = soup.select(TRANSPORTATION_DETAIL_SECTION_SELECTOR)
    detail_list = []
    for detail in transportation_details:
        detail_item = extract_transportation_details(detail)
        if detail_item is not None:
            detail_list.append(detail_item)

    if len(detail_list) > 0:
        output_data["transportation"] = detail_list


def extract_environment(soup, output_data):
    transit_score = soup.select_one(TRANSIT_SCORE_SELECTOR)
    bike_score = soup.select_one(BIKE_SCORE_SELECTOR)
    walk_score = soup.select_one(WALK_SCORE_SELECTOR)

    data_entry = {}
    if transit_score is not None:
        data_entry["transit_score"] = transit_score.get_text().strip()

    if bike_score is not None:
        data_entry["bike_score"] = bike_score.get_text().strip()

    if walk_score is not None:
        data_entry["walk_score"] = walk_score.get_text().strip()

    sound_score_section = soup.select_one(SOUND_SCORE_SECTION_SELECTOR)
    if sound_score_section is not None:
        sound_score = sound_score_section.select_one(SOUND_SCORE_SELECTOR)
        traffic_level = sound_score_section.select_one(TRAFFIC_LEVEL_SELECTOR)
        busi_level = sound_score_section.select_one(BUSI_LEVEL_SELECTOR)
        airport_level = sound_score_section.select_one(AIRPORT_LEVEL_SELECTOR)
        if sound_score is not None:
            data_entry["sound_score"] = sound_score.get_text().strip()
        if traffic_level is not None:
            data_entry["traffic_level"] = traffic_level.get_text().strip()
        if busi_level is not None:
            data_entry["busi_level"] = busi_level.get_text().strip()
        if airport_level is not None:
            data_entry["airport_level"] = airport_level.get_text().strip()

    if len(data_entry) > 0:
        output_data["environment"] = data_entry


def extract_individual_model(soup):
    result = {}
    overview_section = soup.select_one(PRICE_MODEL_OVERVIEW_SELECTOR)
    if overview_section is None:
        return None

    name = overview_section.select_one(MODEL_NAME_SELECTOR)
    rent = overview_section.select_one(MODEL_RENT_SELECTOR)
    details = overview_section.select(MODEL_DETAILS_SELECTOR)
    result["name"] = name.get_text().strip()
    result["rent"] = rent.get_text().strip()
    detail_list = []
    for detail in details:
        detail_list.append(detail.get_text().strip())
    result["details"] = detail_list

    features = soup.select(MODEL_FEATURES_SELECTOR)
    feature_list = []
    for feature in features:
        feature_list.append(feature.get_text().strip())
    feature_list = list(set(feature_list))
    if len(feature_list) > 0:
        result["features"] = feature_list

    model_units = soup.select(MODEL_UNITS_SELECTOR)
    unit_list = []
    for unit in model_units:
        attributes = unit.attrs
        unit_data = {"name": attributes["data-unit"]}
        sqft_elt = unit.select_one(MODEL_UNITS_SQFT_SELECTOR)
        unit_data["sqft"] = sqft_elt.get_text().strip()
        rent_elt = unit.select_one(MODEL_UNITS_RENT_SELECTOR)
        unit_data["rent"] = rent_elt.get_text().strip()
        unit_list.append(unit_data)
    if len(unit_list) > 0:
        result["units"] = unit_list
    if len(result) > 0:
        return result


def extract_units_model(output_data, price_section):
    models = []
    for model in price_section.select(PRICE_MODEL_SELECTOR):
        indi_model = extract_individual_model(model)
        if indi_model is not None:
            models.append(indi_model)
    if len(models) > 0:
        output_data["models"] = models


def extract_whole_model(soup, output_data):
    model = {}
    details = ["", "", ""]
    model["name"] = "self"
    model["features"] = []
    info_bar = soup.select_one(TOP_MODEL_SELECTOR)
    if info_bar is None:
        return
    for info in info_bar.select("li"):
        info_name = info.select_one(TOP_INFO_NAME_SELECTOR).text.strip().lower()
        info_content = info.select_one(TOP_INFO_CONTENT_SELECTOR).text.strip()

        if info_name == "monthly rent":
            model["rent"] = info_content
        if info_name == "bedrooms":
            details[0] = info_content
        if info_name == "bathrooms":
            details[1] = info_content
        if info_name == "square feet":
            details[2] = info_content
    model["details"] = details
    output_data["models"] = [model]


def extract_model(soup, output_data):
    price_section = soup.select_one(PRICE_SECTION_SELECTOR)
    if price_section is not None:
        extract_units_model(output_data, price_section)
    elif output_data["type"] != "Home":
        extract_whole_model(soup, output_data)

def extract_data(key, input_data):
    soup = bs4.BeautifulSoup(input_data["html"], "html.parser")
    output = dict(input_data)
    del output["html"]
    extract_header(soup, output)
    extract_apartment_desc(soup, output)
    extract_amenities(soup, output)
    extract_fees(soup, output)
    extract_neighbor_desc(soup, output)
    extract_education(soup, output)
    extract_nearby_transportation(soup, output)
    extract_environment(soup, output)
    extract_model(soup, output)
    return key, output


def load_json_from(input_dir):
    input_data = {}

    for file in os.listdir(input_dir):
        full_path = os.path.join(input_dir, file)
        if ".json" in file and os.path.isfile(full_path):
            with open(full_path, "r") as fp:
                data = json.load(fp)
                input_data[file] = data
    return input_data


if __name__ == "__main__":
    input_dir = sys.argv[1]
    output_dir = sys.argv[2]
    input_data = load_json_from(input_dir)

    with mp.Pool(PROCESS_COUNT) as pool:
        results = []
        for key in input_data:
            data = input_data[key]
            results.append(pool.apply_async(extract_data, (key, data)))
        for res in results:
            key, output = res.get()
            print("Finished Extracting: %s" % key)
            path = os.path.join(output_dir, key)
            with open(path, "w") as fp:
                json.dump(output, fp)
