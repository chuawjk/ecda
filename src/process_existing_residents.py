from pathlib import Path
from typing import List, Union

import pandas as pd


class ExistingResidentsProcessor:
    """
    Processes existing residents data to extract women by age bin for each subzone.
    """

    def __init__(
        self,
        existing_residents_path: Union[str, Path],
        sheet_name: str = "2020",
        header_row: int = 2,
    ):
        """
        Initializes the ExistingResidentsProcessor.

        Args:
            existing_residents_path: Path to the Excel file with existing residents data.
            sheet_name: Name of the Excel sheet to read.
            header_row: Row number to use as header (0-indexed).
        """
        self.existing_residents_path = existing_residents_path
        self.sheet_name = sheet_name
        self.header_row = header_row
        
        # Age groups for childbearing women
        self.all_mother_ages = [
            "15 - 19 Years", "20 - 24 Years", "25 - 29 Years", 
            "30 - 34 Years", "35 - 39 Years", "40 - 44 Years", "45 - 49 Years"
        ]
        
        # Initialize data containers
        self.existing_residents_data = None
        self.existing_residents_in_subzones = None
        self.existing_women_by_age_bin = None
        self.age_bins = None

    def load_existing_residents_data(self) -> pd.DataFrame:
        """
        Loads existing residents data from Excel file.

        Returns:
            Raw pandas DataFrame with existing residents data.
        """
        print(f"Loading existing residents data from {self.existing_residents_path}")
        self.existing_residents_data = pd.read_excel(
            self.existing_residents_path, 
            sheet_name=self.sheet_name, 
            header=self.header_row
        )
        return self.existing_residents_data

    def clean_existing_residents_data(self) -> pd.DataFrame:
        """
        Cleans the existing residents data by filtering out totals and keeping only female residents.

        Returns:
            Cleaned pandas DataFrame with subzone-level female residents by age.
        """
        print("Cleaning existing residents data...")
        
        # Filter out total rows and keep only females
        cleaned_data = self.existing_residents_data[
            self.existing_residents_data["Subzone"] != "Total"
        ]
        cleaned_data = cleaned_data[cleaned_data["Age"] != "Total"]
        cleaned_data = cleaned_data[cleaned_data["Sex"] != "Total"]
        cleaned_data = cleaned_data[cleaned_data["Sex"] != "Males"]
        
        # Select relevant columns and rename
        year_column = int(self.sheet_name)  # Assuming sheet name is the year
        cleaned_data = cleaned_data[["Subzone", "Age", year_column]].copy()
        cleaned_data.rename(columns={year_column: "Count"}, inplace=True)
        
        # Convert Count to numeric, handling any non-numeric values
        cleaned_data["Count"] = pd.to_numeric(cleaned_data["Count"], errors='coerce')
        
        self.existing_residents_in_subzones = cleaned_data
        return self.existing_residents_in_subzones

    def get_age_bins(self) -> dict:
        """
        Creates mapping from individual ages to age bins.

        Returns:
            Dictionary mapping age strings to age bin names.
        """
        print("Creating age bins mapping...")
        
        age_bins = {
            str(age): bin_name
            for bin_name in self.all_mother_ages
            for age in range(
                int(bin_name.split(" - ")[0]), 
                int(bin_name.split(" - ")[1].replace(" Years", "")) + 1
            )
        }
        
        self.age_bins = age_bins
        return self.age_bins

    def aggregate_women_by_age_bin(self) -> pd.DataFrame:
        """
        Aggregates women counts by subzone and age bin.

        Returns:
            DataFrame with women counts by subzone and age bin.
        """
        print("Aggregating women by age bin...")
        
        # Create a copy to avoid modifying original data
        women_by_age_bin = self.existing_residents_in_subzones.copy()
        
        # Map ages to age bins
        women_by_age_bin["Age Bin"] = women_by_age_bin["Age"].astype(str).map(self.age_bins)
        
        # Drop rows where mapping failed
        women_by_age_bin = women_by_age_bin.dropna(subset=["Count", "Age Bin"])
        
        # Group by subzone and age bin
        women_by_age_bin = women_by_age_bin.groupby(["Subzone", "Age Bin"])["Count"].sum()
        women_by_age_bin = pd.DataFrame(women_by_age_bin).reset_index()
        
        self.existing_women_by_age_bin = women_by_age_bin
        return self.existing_women_by_age_bin

    def run(self) -> pd.DataFrame:
        """
        Main method that orchestrates the entire processing pipeline.

        Returns:
            DataFrame with women counts by subzone and age bin.
        """
        print("Processing existing residents data...")
        
        # Load and process the data
        self.load_existing_residents_data()
        self.clean_existing_residents_data()
        self.get_age_bins()
        self.aggregate_women_by_age_bin()
        
        print(f"Processed {len(self.existing_women_by_age_bin)} records across {len(self.existing_women_by_age_bin['Subzone'].unique())} subzones")
        
        return self.existing_women_by_age_bin


if __name__ == "__main__":
    # Example usage
    existing_processor = ExistingResidentsProcessor(
        existing_residents_path=Path("data/respopagesex2000to2020e.xlsx")
    )
    
    existing_women_by_age_bin = existing_processor.run()
    print(existing_women_by_age_bin.head())