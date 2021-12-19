import os
import pandas as pd
import geopandas as gpd
import altair as alt
from altair_saver import save
from matplotlib import pyplot as plt

alt.data_transformers.disable_max_rows()
census_state_fips	=	{'CA': '06'}
full_state_names	=	{'CA': 'California'}
data 				=	"data/%s"
census_data			=	data % "census/%s"
emissions_data		=	data % "emissions"
income_data 		=	census_data % "income"
tract_data			=	census_data % "tracts/%s/%s"
#read a csv of I generated to map column names
income_col_map		=	pd.read_csv(os.path.join(income_data, 'columnMap.csv'))
income_col_map		=	{k: v for k, v in zip(income_col_map['raw'], income_col_map['clean'])}
pct_columns			=	['pct_below10k', 'pct_10k_14k', 'pct_15k_24k', 'pct_25k_34k', 'pct_35k_49k']

def distributions(dfList, colList, file_name, file_type='.png'):
	plots = []
	for df, col in list(zip(dfList, colList)):
		plots.append(alt.Chart(df).transform_density(col, as_=[col, 'density']).mark_area().encode(\
																					x="%s:Q" % col,\
																					y="density:Q"))
	plot =	None
	for i, x in enumerate(plots):
		if plot:
			plot = alt.layer(plot, x)
		else:
			plot = x

	save(plot, 'plots/' + file_name + file_type)

def distribution(df, col, file_name, file_type='.png'):
	chart	=	alt.Chart(df).transform_density(col, as_=[col, 'density']).mark_area().encode(\
																					x="%s:Q" % col,\
																					y="density:Q").properties(\
																					title=file_name)
	chart.configure_title(fontSize=20,\
							font='Arial',\
							anchor='start',\
							color='blue')
	save(chart, 'plots/' + file_name + file_type)

def get_tracts(year, state):
	'''
	census tracts stored in year/state_fips_code tree structure
	year and fipsCode can be string or int, function will add leading
	0's as necessary to type-enforced s_year and s_code
	'''
	s_year		=	str(year)
	s_code 		=	census_state_fips[state]
	file_pattern=	'tl_%s_%s_tract.shp'
	full_path	=	os.path.join(tract_data % (s_year, s_code), file_pattern % (s_year, s_code))

	return gpd.read_file(os.path.join(full_path))

def get_income_data(year):
	'''
	read income data from a specific year of Census ACS data
	
	map descriptive names to  columns we will be using
	'''
	acs_income_pattern	=	"ACSDP5Y%s.DP03_data_with_overlays_2021-11-10T125614.csv"
	numeric 			=	['pct_below10k',
								'pct_10k_14k',
								'pct_15k_24k',
								'pct_25k_34k',
								'pct_35k_49k',
								'medianEarnings',
								'pct_below_poverty']

	df 					=	pd.read_csv(os.path.join(income_data, (acs_income_pattern % str(year))))
	df 					=	df.loc[:, [x for x in df.columns if x in income_col_map.keys()]].rename(columns=income_col_map).iloc[1:, :]

	for col in numeric:
		df.loc[:, col]	=	df.loc[:, col].apply(lambda x: x if '-' not in x else 0).astype(float)

	return df


def get_census_data(year, state):
	'''
	merge the tracts and income data
	'''
	tracts 	=	get_tracts(year, state)
	#the only income data I have at the moment
	income 	=	get_income_data(2019)

	#cut off part of geo id in income that is not included in tracts' geoid
	income.loc[:, 'geo_id']	=	income.loc[:, 'geo_id'].apply(lambda x: x[9:])

	return pd.merge(tracts, income, left_on='GEOID', right_on='geo_id')

def get_emissions_data(state):
	'''
	https://www.epa.gov/airmarkets/power-plant-data-viewer

	epa's power plant data viewer provides all of the information we need here

	unfortunately, we need to make a separate column for each of  the pollutants,
	that will be handled in this function

	we also want to return a GeoDataFrame with the lat and long columns made into a point. first,
	set crs to epsg=4326 to read in per epa technical specification:
	https://www.epa.gov/geospatial/epa-metadata-technical-specification
	and then reproject into 4269, which is used by the census
	'''
	raw 			=	pd.read_csv(os.path.join(emissions_data, 'power_plant_data_viewer_data.csv'))
	raw.columns		=	[x.strip() for x in raw.columns]
	raw 			=	raw.rename(columns={'Facility Name': 'facility_name', 'State':'state',\
										'Year': 'year', 'Latitude': 'latitude', 'Longitude': 'longitude',\
										'Pollutant': 'pollutant', 'Emissions (tons)': 'emitted_tons',\
										'Heat Input (mmBtu)': 'heat_input'})
	raw 			=	raw.loc[raw.state == full_state_names[state]]
	raw				=	raw.set_index(['facility_name', 'year'])
	pollutants		=	['SO2', 'CO2', 'NOx']
	df 				=	pd.DataFrame(index=list(set(raw.index)))
	#collect emitted tons by pollutant for each facility-year
	#be sure to clean out the commas and convert these to floats as well
	#keep in mind that these columns have mixed data types
	for p in pollutants:
		idx 			=	raw.loc[raw.pollutant == p].index
		df.loc[idx, p]	=	raw.loc[raw.pollutant  == p, 'emitted_tons'].apply(lambda x: float(str(x).replace(",",  "")))
	#only information left to copy from raw now lat/longs
	raw				=	raw.loc[~raw.index.duplicated(keep='first')]
	df['latitude']	=	raw.loc[df.index, 'latitude']
	df['longitude']	=	raw.loc[df.index, 'longitude']
	#read in with specified projection and reproject to match census
	df 				=	gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df.loc[:, 'longitude'], df.loc[:, 'latitude'])).set_crs(epsg=4326)
	#reproject
	df 				=	df.to_crs(epsg=4269)

	return	df
