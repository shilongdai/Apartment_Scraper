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

STATE_ZIP_REGEX = "stateZipContainer"
NEIGHBOR_REGEX = "neighborhoodAddress"


def extract_address_part(index, part, output_data):
    if index == 0:
        output_data["address"] = part.get_text()
        return
    if index == 1:
        output_data["city"] = part.get_text()
        return
    if "class" not in part.attrs:
        return
    if re.match(STATE_ZIP_REGEX, part.attrs["class"][0]):
        output_data["state_zip"] = part.get_text().strip().replace("\n", " ")
        return
    if re.match(NEIGHBOR_REGEX, part.attrs["class"][0]):
        output_data["neighborhood"] = part.get_text().strip()[2:]
        return


def extract_header(soup, output_data):
    header_section = soup.select_one(PROPERTY_HEADER_SECTION_SELECTOR)
    address_section = header_section.select_one(PROPERTY_ADDRESS_SECTION_SELECTOR)
    address_parts = address_section.select(ADDRESS_PART_SELECTOR)
    for i, part in enumerate(address_parts):
        extract_address_part(i, part, output_data)


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
        note_content_text = note_section.find(text=True, recursive=False).strip()
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


def extract_data(key, input_data):
    soup = bs4.BeautifulSoup(input_data["html"], "html.parser")
    output = {}
    extract_header(soup, output)
    extract_apartment_desc(soup, output)
    extract_amenities(soup, output)
    extract_fees(soup, output)
    return key, output


if __name__ == "__main__":
    input_dir = sys.argv[1]
    output_dir = sys.argv[2]
    input_data = {}

    for file in os.listdir(input_dir):
        full_path = os.path.join(input_dir, file)
        if ".json" in file and os.path.isfile(full_path):
            with open(full_path, "r") as fp:
                data = json.load(fp)
                input_data[file] = data

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
