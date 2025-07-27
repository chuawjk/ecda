
import matplotlib.pyplot as plt
import pandas as pd


def prepare_mapping_data_merge(
    existing_preschools_by_subzone,
    forecasted_num_preschoolers,
    forecasted_num_preschools_needed,
    preschool_gap,
    year=2030,
):
    """Alternative approach using explicit merge operations."""

    # Start with subzone geographic data
    map_data = existing_preschools_by_subzone.copy()

    # Prepare forecast data as DataFrames for merging
    forecast_data = pd.DataFrame(
        {
            "subzone_name_clean": forecasted_num_preschoolers.columns,
            "projected_preschoolers": forecasted_num_preschoolers.loc[year].values,
            "preschools_needed": forecasted_num_preschools_needed.loc[year].values,
            "preschool_gap": preschool_gap.loc[year].values,
        }
    )

    # Merge with geographic data
    map_data = map_data.merge(forecast_data, on="subzone_name_clean", how="left")

    # Fill missing values with 0
    forecast_cols = ["projected_preschoolers", "preschools_needed", "preschool_gap"]
    map_data[forecast_cols] = map_data[forecast_cols].fillna(0)

    # Calculate derived columns
    map_data["shortage"] = -map_data["preschool_gap"].clip(upper=0)
    map_data["surplus"] = map_data["preschool_gap"].clip(lower=0)

    # Set index for mapping
    map_data = map_data.set_index("subzone_name_clean")

    return map_data


def plot_preschool_analysis(map_data, year=2030):
    """
    Create a multi-panel visualization showing preschool demand analysis by subzone.

    Args:
        map_data: GeoDataFrame containing subzone geometries and analysis data
        year: Year to display in titles (default 2030)
    """
    # Multi-panel demand/supply analysis map
    fig, axes = plt.subplots(2, 2, figsize=(20, 16))
    fig.suptitle(
        f"Preschool Demand Analysis by Subzone ({year})", fontsize=16, fontweight="bold"
    )

    # 1. Current Supply
    ax1 = axes[0, 0]
    map_data.plot(
        column="num_preschools",
        ax=ax1,
        legend=True,
        cmap="Blues",
        edgecolor="white",
        linewidth=0.5,
    )
    ax1.set_title("Current Childcare Centres", fontweight="bold")
    ax1.axis("off")

    # 2. Projected Demand
    ax2 = axes[0, 1]
    map_data.plot(
        column="projected_preschoolers",
        ax=ax2,
        legend=True,
        cmap="Oranges",
        edgecolor="white",
        linewidth=0.5,
    )
    ax2.set_title(f"Projected Preschoolers ({year})", fontweight="bold")
    ax2.axis("off")

    # 3. Preschools Needed
    ax3 = axes[1, 0]
    map_data.plot(
        column="preschools_needed",
        ax=ax3,
        legend=True,
        cmap="Reds",
        edgecolor="white",
        linewidth=0.5,
    )
    ax3.set_title(f"Preschools Needed ({year})", fontweight="bold")
    ax3.axis("off")

    # 4. Shortage Areas (Priority Zones)
    ax4 = axes[1, 1]
    shortage_data = map_data[map_data["shortage"] > 0]
    map_data.plot(color="lightgray", ax=ax4, edgecolor="white", linewidth=0.5)
    shortage_data.plot(
        column="shortage",
        ax=ax4,
        legend=True,
        cmap="Reds",
        edgecolor="darkred",
        linewidth=1,
    )
    ax4.set_title("Preschool Shortages (Red = Priority Areas)", fontweight="bold")
    ax4.axis("off")

    plt.tight_layout()
    plt.show()
    plt.close()
