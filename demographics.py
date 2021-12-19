import geopandas as gpd
import altair as alt
from altair_saver import save
from pandas import DataFrame, merge, qcut, crosstab
from utils import get_census_data, get_emissions_data, pct_columns, distribution

'''
a quick look at which parts of California took on the largest share of emissions
'''


census 				=	get_census_data(2020, 'CA')
emissions 			=	get_emissions_data('CA')

#some initial distributions from the census
distribution(census, 'pct_below_poverty', 'Percent Below Poverty by Tract')
distribution(census, 'medianEarnings', 'Median Earnings by Tract')
census['below35k']	=	census[pct_columns].sum(axis=1)
distribution(census, 'pct_below_poverty', 'Percent Below Poverty by Tract')

#first, lets sort the power plants into their respective census tracts and look at the distribution
#of CO2, SO2, and NOx emitted directly into each tract, then plot the map
inside		=	census.sjoin(emissions, how='left', predicate='contains')
CO2 		=	DataFrame(inside.groupby('GEOID').CO2.sum())
SO2 		=	DataFrame(inside.groupby('GEOID').SO2.sum())
NOx 		=	DataFrame(inside.groupby('GEOID').NOx.sum())
distribution(CO2, 'CO2', 'CO2 Emissions by Tract')
distribution(SO2, 'SO2', 'SO2 Emissions by Tract')
distribution(NOx, 'NOx', 'NOx Emissions by Tract')
#convert everything back to epsg:4326 to use altair
#when using geoms from census remember they start with epsg:4269
# pEmissions 	=	emissions.to_crs(epsg=4326) (p is for plottable)
geo_ids					=	list(inside.GEOID.unique())
by_tract				=	DataFrame(index=geo_ids)
tracts					=	inside.groupby('GEOID').geometry.first()
by_tract['geometry']	=	tracts.loc[by_tract.index]
by_tract				=	gpd.GeoDataFrame(by_tract, geometry='geometry').set_crs(epsg=4269)
by_tract				=	by_tract.to_crs(epsg=4326)

#make a clean up correctly projected 'tracts' as a background:
for df, col in [(CO2, 'CO2'), (SO2, 'SO2'), (NOx, 'NOx')]:
	df 		=	df.reset_index()
	merged	=	merge(census, df, on='GEOID')
	chart 	=	alt.Chart(merged).mark_geoshape().encode(\
											alt.Color(col,\
											scale=alt.Scale(scheme='bluegreen'))).project(\
																		type='albersUsa').properties(\
																							title="%s by Tract - Mapped" % col,\
																							width=500,\
																							height=300)
	# plotme 	=	bg + chart
	save(chart, "plots/%s by Tract - Mapped.png" % col)

#now lets investigate what relationship poverty rates may have with dealing with more NOx, which seems to have the most differences between tracts
merged				=	merge(census, NOx, on='GEOID')
#only 73 tracts affected by NOx, filter away 0's
merged				=	merged.loc[merged.NOx != 0]
merged['binnedNOx'] =	qcut(merged.NOx, [0, .25, .5, .75, 1], ['Low', 'Medium', 'High', 'Extreme'])
merged['binnedPov'] =	qcut(merged.pct_below_poverty, [0, .25, .5, .75, 1], ['None', 'Low', 'Medium', 'High', 'Extreme'])
print(crosstab(merged.binnedNOx, merged.binnedPov))
#save this
crosstab(merged.binnedNOx, merged.binnedPov).to_csv('NOx - Poverty Rate Crosstab.csv')






