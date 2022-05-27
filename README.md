# Apartment_Scraper

This is a python + selenium + bs4 based webscraper used to extract apartment data from apartments.com. The final output is a json file with the desired apartment informations, and a csv file with apartments in vector forms.

## Sample Output

The sample output from scanning one apartment can be found in the repository at sample_compile.json and sample_compile.csv

## Usage

First, edit the config.ini file to point the _DRIVER_ field to the path of the chromedriver. Then, update the _URL_TEMPLATE_ to be pointed to the search result page of apartments.com for a given area. The two placeholder %d in the templates are used to narrow down the price range of the search results so that the 28 page limitation is avoided.

After the config is done, execute the script:

```
python scrape.py
```

It will output a urls.json file containing the url to all the individual apartment pages.

Then, create a pages directory in the current working directory and execute:

```
python download.py urls.json pages/
```

This will download the html of all the apartment pages in the urls.json file.

After the download is complete, create an extract directory in the current working directory and execute:

```
python extract.py pages/ extract/
```

This will extract all the relevant strings from the html page and write the results to the extract directory in json format.

Finally, after the extraction is complete, run:

```
python compile.py extract/
```

to format the data and output a final .json and .csv file.
