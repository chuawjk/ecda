import html
import re
import requests
from pathlib import Path
from typing import Optional, Tuple, Union

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point


class PreschoolProcessor:
    """
    Processes data of existing preschools to compute the number of existing preschools in each subzone.
    """

    def __init__(
        self,
        subzone_data_path: Union[str, Path],
        crs: str,
        raw_preschool_data_path: Union[str, Path],
        processed_preschool_data_path: Optional[Union[str, Path]] = None,
    ):
        """
        Initializes the PreschoolProcessor.

        Loads preprocessed preschool data if available, otherwise loads raw data and preprocesses it.

        Args:
            subzone_data_path: The path to GEOJSON file containing subzone geolocation definitions.
            crs: The coordinate reference system of the subzone data.
            raw_preschool_data_path: The path to the raw preschool data CSV.
            processed_preschool_data_path: The path to the preprocessed preschool data CSV.
        """
        self.subzone_data = gpd.read_file(subzone_data_path)
        self.subzone_data = self.subzone_data.set_crs(crs, allow_override=True)

        if (
            processed_preschool_data_path is not None
            and Path(processed_preschool_data_path).exists()
        ):
            print("Preprocessed preschool data found, skipping preprocessing")
            print(
                f"Loading preprocessed preschool data from {processed_preschool_data_path}"
            )
            self.processed_preschool_data = pd.read_csv(processed_preschool_data_path)
            self.raw_preschool_data = None
        else:
            print("No preprocessed preschool data found")
            print(f"Loading raw preschool data from {raw_preschool_data_path}")
            self.raw_preschool_data = pd.read_csv(raw_preschool_data_path)
            self.processed_preschool_data = None

    def get_latlon_from_postal(
        self, postal_code: int
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Query OneMap's Search API to convert a 6-digit Singapore postal code
        into (latitude, longitude).

        Returns:
            (lat, lon) as floats, or None if no result is found.
        """
        postal_code = str(postal_code)
        url = f"https://www.onemap.gov.sg/api/common/elastic/search?searchVal={postal_code}&returnGeom=Y&getAddrDetails=Y&pageNum=1"
        headers = {"Authorization": "Bearer **********************"}
        response = requests.get(url, headers=headers).json()

        try:
            # Get first result
            if int(response["found"]) > 0:
                result = response["results"][0]
                return float(result["LATITUDE"]), float(result["LONGITUDE"])
            else:
                print(f"No result found for postal code {postal_code}")
                return None, None
        except Exception as e:
            print(f"Error getting latlon from postal code {postal_code}: {e}")
            return None, None

    def get_preschool_latlon(self, preschool_data: pd.DataFrame) -> pd.DataFrame:
        """
        Get the latitude and longitude of all preschools.

        Args:
            preschool_data: DataFrame containing preschool postal code in "postal_code" column

        Returns:
            DataFrame: preschool_data with new 'latitude' and 'longitude' columns
        """
        print(
            f"Calling OneMap API for {len(preschool_data)} instances, this may take a while..."
        )
        preschool_data["latitude"], preschool_data["longitude"] = zip(
            *preschool_data.apply(
                lambda x: self.get_latlon_from_postal(int(x["postal_code"])), axis=1
            )
        )
        return preschool_data

    def compute_missing_latlon_pct(self, preschool_data: pd.DataFrame) -> None:
        """
        Compute the percentage of preschools with missing latitude and longitude.
        """
        missing_coords = preschool_data[
            preschool_data["latitude"].isna() | preschool_data["longitude"].isna()
        ]
        missing_pct = len(missing_coords) / len(preschool_data) * 100
        print(f"{missing_pct:.1f}% of preschools have missing coordinates")

    def extract_subzone_name(self, description_html: str) -> str:
        """
        Extract subzone name from HTML description and convert to title case.

        Args:
            description_html: HTML string containing subzone information

        Returns:
            str: Cleaned subzone name in title case
        """
        # Pattern to match the SUBZONE_N row in the HTML table
        # Looks for: <th>SUBZONE_N</th> <td>SUBZONE_NAME</td>
        pattern = r"<th>SUBZONE_N<\/th>\s*<td>([^<]+)<\/td>"

        match = re.search(pattern, description_html)

        if match:
            # Extract the subzone name
            subzone_name = match.group(1)

            # Unescape any HTML entities (though there shouldn't be any in this case)
            subzone_name = html.unescape(subzone_name)

            # Convert from ALL CAPS to Title Case
            subzone_name_clean = subzone_name.title()

            return subzone_name_clean
        else:
            # Fallback: try to extract any text that looks like a subzone name
            # This handles cases where the HTML structure might be slightly different
            fallback_pattern = r"SUBZONE_N.*?<td>([^<]+)<\/td>"
            fallback_match = re.search(
                fallback_pattern, description_html, re.IGNORECASE
            )

            if fallback_match:
                return fallback_match.group(1).title()
            else:
                return "Unknown Subzone"

    def clean_subzone_names(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Add a clean subzone name column to the GeoDataFrame.

        Args:
            gdf: GeoDataFrame with 'Description' column containing HTML

        Returns:
            GeoDataFrame: Original data with new 'subzone_name_clean' column
        """
        # Extract clean subzone names
        gdf["subzone"] = gdf["Description"].apply(self.extract_subzone_name)

        return gdf

    def drop_subzone_columns(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        Drop all columns except "geometry" and "subzone".
        """
        return gdf[["geometry", "subzone"]]

    def count_childcare_centres_per_subzone(
        self, subzone_data: gpd.GeoDataFrame, preschool_data: pd.DataFrame
    ) -> gpd.GeoDataFrame:
        """
        Count number of existing preschools that fall within each subzone.

        Args:
            subzones_data: GeoDataFrame containing subzone polygons
            preschool_data: DataFrame containing preschool latitude and longitude columns

        Returns:
            GeoDataFrame: subzones_data with new 'num_childcare_centres' column
        """
        # Initialize column to count childcare centres per subzone
        subzone_data["num_preschools"] = 0

        # Process each childcare centre
        for _, preschool in preschool_data.iterrows():
            # Skip if no lat/lon available
            if pd.isna(preschool.latitude) or pd.isna(preschool.longitude):
                continue

            # Create point geometry from lat/lon
            point = Point(preschool.longitude, preschool.latitude)

            # Find which subzone contains this point
            for idx, subzone in subzone_data.iterrows():
                if point.within(subzone.geometry):
                    subzone_data.loc[idx, "num_preschools"] += 1
                    break

        return subzone_data

    def run(self) -> pd.DataFrame:
        """
        Runs the PreschoolProcessor to get the number of existing preschools in each subzone.
        """
        if self.processed_preschool_data is None:
            # Process raw data: add lat/lon to preschools
            preschool_data = self.get_preschool_latlon(self.raw_preschool_data)
            # Save raw preschool data with lat/lon for future use
            preschool_data.to_csv(Path("data/preschools_data_processed.csv"), index=False)
            self.compute_missing_latlon_pct(preschool_data)
        else:
            # Use existing processed preschool data
            preschool_data = self.processed_preschool_data
        
        # Always perform subzone aggregation (this is what we actually want to return)
        self.subzone_data = self.clean_subzone_names(self.subzone_data)
        # self.subzone_data = self.drop_subzone_columns(self.subzone_data)
        subzone_with_counts = self.count_childcare_centres_per_subzone(
            self.subzone_data, preschool_data
        )
        
        # Add subzone_name_clean column for merging with forecast data
        subzone_with_counts = subzone_with_counts.reset_index()
        subzone_with_counts['subzone_name_clean'] = subzone_with_counts['subzone']
        subzone_with_counts = subzone_with_counts.set_index('subzone_name_clean')
        
        return subzone_with_counts


if __name__ == "__main__":
    preschool_processor = PreschoolProcessor(
        subzone_data_path=Path(
            "data/Master Plan 2019 Subzone Boundary (No Sea) (GEOJSON).geojson"
        ),
        crs="urn:ogc:def:crs:OGC:1.3:CRS84",
        raw_preschool_data_path=Path("data/ListingofCentres.csv"),
        processed_preschool_data_path=Path("data/preschools_data_processed.csv"),
    )
    preschool_processor.run()
