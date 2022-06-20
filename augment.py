import json
from datetime import datetime

import googlemaps
import pandas as pd

API_KEY = "KEY"
ADDR_TEMPLATE = "%s, %s, %s"
DEST = ["The University of Chicago"]


def fetch_geo(addresses):
    data_dict = {"address": [], "lat": [], "lng": []}
    for addr in set(addresses):
        retry = 0
        while retry < 3:
            try:
                geocode = gmaps.geocode(addr)
            except:
                print("Failed to fetch geo: " + addr)
                retry = retry + 1
                continue
            try:
                geocode_elt = geocode[0]["geometry"]["location"]
                lat = geocode_elt["lat"]
                lng = geocode_elt["lng"]
            except (IndexError, KeyError):
                print("Failed to find lat, lng for: " + addr)
                print(geocode)
                retry = retry + 1
                continue
            data_dict["address"].append(addr)
            data_dict["lat"].append(lat)
            data_dict["lng"].append(lng)
            if len(data_dict["address"]) % 500 == 0:
                print("%d/%d" % (len(data_dict["address"]), len(set(addresses))))
            break
        if retry == 3:
            print("All 3 retries failed for: " + addr)
    return data_dict


def fetch_transit(addresses):
    data_dict = {"address": [], "distance": [], "walk.time": [], "transit.time": []}
    time = datetime.now()
    time = time.replace(month=6, day=20, hour=9, minute=30)
    for addr in set(addresses):
        retry = 0
        while retry < 3:
            try:
                matrix_walk = gmaps.distance_matrix(addr, DEST, mode="walking", departure_time=time)
                matrix_transit = gmaps.distance_matrix(addr, DEST, mode="transit", departure_time=time)
            except:
                print("Failed to fetch transit: " + addr)
                retry = retry + 1
                continue
            try:
                walk_elt = matrix_walk["rows"][0]["elements"][0]
                transit_elt = matrix_transit["rows"][0]["elements"][0]
                distance = walk_elt["distance"]["value"]
                walk_time = walk_elt["duration"]["value"] / 60
            except (IndexError, KeyError):
                print("Failed to get transportation info: " + addr)
                retry = retry + 1
                continue
            try:
                transit_time = transit_elt["duration"]["value"] / 60
            except KeyError:
                print("Failed to find transit for: " + addr)
                retry = retry + 1
                continue
            data_dict["address"].append(addr)
            data_dict["distance"].append(distance)
            data_dict["walk.time"].append(walk_time)
            data_dict["transit.time"].append(transit_time)
            if len(data_dict["distance"]) % 500 == 0:
                print("%d/%d" % (len(data_dict["distance"]), len(set(addresses))))
            break
        if retry == 3:
            print("All 3 retries failed for: " + addr)
    return data_dict


if __name__ == "__main__":
    gmaps = googlemaps.Client(key=API_KEY)
    with open("compile.json", "r") as fp:
        apartments = json.load(fp)
    addresses = []
    for p in apartments:
        addresses.append(ADDR_TEMPLATE % (p["address"], p["city"], p["state"]))

    transit_dict = fetch_transit(addresses)
    transit_df = pd.DataFrame(transit_dict)
    transit_df.to_csv("transport.csv", index=False)
    geo_dict = fetch_geo(addresses)
    geo_df = pd.DataFrame(geo_dict)
    geo_df.to_csv("geo.csv", index=False)
