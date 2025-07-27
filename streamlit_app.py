import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import tempfile
import json
from pathlib import Path
import folium
from streamlit_folium import st_folium

# Import our forecast system
from src.forecast import Forecaster, Config
from src.visualizations import prepare_mapping_data_merge


def main():
    """Main Streamlit application for preschool demand forecasting."""

    # Set page configuration
    st.set_page_config(
        page_title="Singapore Preschool Demand Forecasting",
        page_icon="🏫",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # Main title and description
    st.title("🏫 Singapore Preschool Demand Forecasting")
    st.markdown("""
    This application forecasts preschool demand across Singapore subzones using:
    - **Fertility data**: Birth rates by age group over time
    - **BTO housing data**: New housing completions by subzone
    - **Existing residents data**: Current population demographics by age and subzone
    - **Existing preschool data**: Current childcare center locations
    - **Geographic data**: Subzone boundary definitions
    """)

    # Initialize session state
    if 'forecast_results' not in st.session_state:
        st.session_state.forecast_results = None
    if 'uploaded_files' not in st.session_state:
        st.session_state.uploaded_files = {}

    # Sidebar for configuration
    with st.sidebar:
        st.header("⚙️ Configuration")
        config = setup_configuration_panel()

    # Main content area
    col1, col2 = st.columns([1, 1])

    with col1:
        st.header("📁 Data Upload")
        uploaded_files = setup_file_upload_section()

    with col2:
        st.header("🚀 Forecast Execution")
        if st.button("Run Forecast", type="primary", use_container_width=True):
            if validate_inputs(uploaded_files):
                with st.spinner("Running forecast analysis..."):
                    results = run_forecast_analysis(config, uploaded_files)
                    if results:
                        st.session_state.forecast_results = results
                        st.success("Forecast completed successfully!")
                        st.rerun()
            else:
                st.error("Please upload all required data files first.")

    # Results visualization section
    if st.session_state.forecast_results:
        st.header("📊 Forecast Results & Visualization")
        display_forecast_results()


def setup_configuration_panel():
    """Setup the configuration panel in the sidebar."""
    st.subheader("Forecast Parameters")

    # Forecasting parameters
    num_forecast_years = st.slider(
        "Number of forecast years",
        min_value=1,
        max_value=10,
        value=5,
        help="How many years into the future to forecast"
    )

    preschool_capacity = st.number_input(
        "Preschool capacity (children per center)",
        min_value=50,
        max_value=200,
        value=100,
        step=10,
        help="Average number of children each preschool can accommodate"
    )

    st.subheader("Age Parameters")

    min_preschool_age = st.slider(
        "Minimum preschool age (months)",
        min_value=12,
        max_value=36,
        value=18,
        help="Minimum age when children start preschool"
    )

    max_preschool_age = st.slider(
        "Maximum preschool age (months)",
        min_value=60,
        max_value=84,
        value=72,
        help="Maximum age when children attend preschool"
    )

    st.subheader("Existing Residents Parameters")

    sheet_name = st.text_input(
        "Excel sheet name for existing residents data",
        value="2020",
        help="Name of the Excel sheet containing population data"
    )

    header_row = st.number_input(
        "Header row number (0-indexed)",
        min_value=0,
        max_value=10,
        value=2,
        step=1,
        help="Row number to use as column headers in the Excel file"
    )

    st.subheader("Geographic Parameters")

    crs = st.text_input(
        "Coordinate Reference System",
        value="urn:ogc:def:crs:OGC:1.3:CRS84",
        help="CRS for geographic data processing"
    )

    # Create config object
    config = Config(
        num_forecast_years=num_forecast_years,
        preschool_capacity=preschool_capacity,
        min_preschool_age=min_preschool_age,
        max_preschool_age=max_preschool_age,
        sheet_name=sheet_name,
        header_row=header_row,
        crs=crs
    )

    return config


def setup_file_upload_section():
    """Setup the file upload section with default file options."""
    uploaded_files = {}

    # Default file paths - separate required from optional
    required_default_files = {
        'fertility_data': 'data/BirthsAndFertilityRatesAnnual.csv',
        'bto_data': 'data/btomapping.csv',
        'existing_residents': 'data/respopagesex2000to2020e.xlsx',
        'subzone_data': 'data/Master Plan 2019 Subzone Boundary (No Sea) (GEOJSON).geojson',
        'preschool_data': 'data/ListingofCentres.csv'
    }
    
    optional_default_files = {
        'processed_preschool': 'data/preschools_data_processed.csv'
    }

    # Check if required default files exist (optional files don't block defaults)
    default_files_exist = all(Path(path).exists() for path in required_default_files.values())

    # Option to use default files
    use_defaults = st.checkbox(
        "🚀 Use default sample data files",
        value=default_files_exist,
        help="Use the sample data files included in the project"
    )

    if use_defaults and default_files_exist:
        st.success("✅ Using default sample data files:")
        
        # Show required files
        for key, path in required_default_files.items():
            st.write(f"- **{key.replace('_', ' ').title()}**: `{path}`")
        
        # Show optional files if they exist
        for key, path in optional_default_files.items():
            if Path(path).exists():
                st.write(f"- **{key.replace('_', ' ').title()}** (optional): `{path}`")
            else:
                st.write(f"- **{key.replace('_', ' ').title()}** (optional): Missing - will be generated")
        
        # Store default file paths (required files always, optional files only if they exist)
        uploaded_files = required_default_files.copy()
        uploaded_files.update({key: path for key, path in optional_default_files.items() if Path(path).exists()})
        uploaded_files['use_defaults'] = True
        
    else:
        st.markdown("📁 Upload your own data files:")
        uploaded_files['use_defaults'] = False

        # File upload widgets with descriptions
        files_config = [
            {
                'key': 'fertility_data',
                'label': 'Fertility Data (CSV)',
                'help': 'Birth rates by age group over years',
                'type': ['csv']
            },
            {
                'key': 'bto_data',
                'label': 'BTO Housing Data (CSV)',
                'help': 'BTO completion data by subzone and year',
                'type': ['csv']
            },
            {
                'key': 'existing_residents',
                'label': 'Existing Residents Data (Excel)',
                'help': 'Population demographics by age, sex, and subzone (Excel file with multiple sheets)',
                'type': ['xlsx', 'xls']
            },
            {
                'key': 'subzone_data',
                'label': 'Subzone Boundaries (GeoJSON)',
                'help': 'Geographic boundaries of Singapore subzones',
                'type': ['geojson', 'json']
            },
            {
                'key': 'preschool_data',
                'label': 'Preschool Data (CSV)',
                'help': 'List of existing childcare centers with locations',
                'type': ['csv']
            }
        ]

        for file_config in files_config:
            uploaded_file = st.file_uploader(
                file_config['label'],
                type=file_config['type'],
                help=file_config['help'],
                key=file_config['key']
            )
            uploaded_files[file_config['key']] = uploaded_file

        # Optional processed preschool data
        st.markdown("---")
        st.markdown("**Optional:** Upload preprocessed preschool data to skip processing:")

        processed_preschool = st.file_uploader(
            "Processed Preschool Data (CSV)",
            type=['csv'],
            help="Pre-processed preschool data with subzone mappings",
            key='processed_preschool'
        )
        uploaded_files['processed_preschool'] = processed_preschool

    return uploaded_files


def validate_inputs(uploaded_files):
    """Validate that all required files are available."""
    required_files = ['fertility_data', 'bto_data', 'existing_residents', 'subzone_data', 'preschool_data']
    
    if uploaded_files.get('use_defaults', False):
        # For default files, check if paths exist
        return all(uploaded_files.get(key) and Path(uploaded_files[key]).exists() 
                  for key in required_files)
    else:
        # For uploaded files, check if file objects exist
        return all(uploaded_files.get(key) is not None for key in required_files)


@st.cache_data
def run_forecast_analysis(config, uploaded_files):
    """Run the forecast analysis with caching."""
    try:
        if uploaded_files.get('use_defaults', False):
            # Use default files directly
            file_paths = {
                'fertility_data_path': Path(uploaded_files['fertility_data']),
                'bto_data_path': Path(uploaded_files['bto_data']),
                'existing_residents_path': Path(uploaded_files['existing_residents']),
                'subzone_data_path': Path(uploaded_files['subzone_data']),
                'raw_preschool_data_path': Path(uploaded_files['preschool_data']),
                'processed_preschool_data_path': (
                    Path(uploaded_files['processed_preschool']) 
                    if uploaded_files.get('processed_preschool') else None
                )
            }
        else:
            # Create temporary directory for uploaded files
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir_path = Path(temp_dir)

                # Save uploaded files to temporary location
                file_paths = {}

                # Save fertility data
                fertility_path = temp_dir_path / "fertility_data.csv"
                with open(fertility_path, "wb") as f:
                    f.write(uploaded_files['fertility_data'].getbuffer())
                file_paths['fertility_data_path'] = fertility_path

                # Save BTO data
                bto_path = temp_dir_path / "bto_data.csv"
                with open(bto_path, "wb") as f:
                    f.write(uploaded_files['bto_data'].getbuffer())
                file_paths['bto_data_path'] = bto_path

                # Save existing residents data
                existing_residents_path = temp_dir_path / "existing_residents.xlsx"
                with open(existing_residents_path, "wb") as f:
                    f.write(uploaded_files['existing_residents'].getbuffer())
                file_paths['existing_residents_path'] = existing_residents_path

                # Save subzone data
                subzone_path = temp_dir_path / "subzone_data.geojson"
                with open(subzone_path, "wb") as f:
                    f.write(uploaded_files['subzone_data'].getbuffer())
                file_paths['subzone_data_path'] = subzone_path

                # Save preschool data
                preschool_path = temp_dir_path / "preschool_data.csv"
                with open(preschool_path, "wb") as f:
                    f.write(uploaded_files['preschool_data'].getbuffer())
                file_paths['raw_preschool_data_path'] = preschool_path

                # Handle optional processed preschool data
                if uploaded_files.get('processed_preschool'):
                    processed_path = temp_dir_path / "processed_preschool_data.csv"
                    with open(processed_path, "wb") as f:
                        f.write(uploaded_files['processed_preschool'].getbuffer())
                    file_paths['processed_preschool_data_path'] = processed_path

        # Update config with file paths
        updated_config = Config(
            num_forecast_years=config.num_forecast_years,
            preschool_capacity=config.preschool_capacity,
            min_preschool_age=config.min_preschool_age,
            max_preschool_age=config.max_preschool_age,
            fertility_data_path=file_paths['fertility_data_path'],
            bto_data_path=file_paths['bto_data_path'],
            existing_residents_path=file_paths['existing_residents_path'],
            sheet_name=config.sheet_name,
            header_row=config.header_row,
            subzone_data_path=file_paths['subzone_data_path'],
            crs=config.crs,
            raw_preschool_data_path=file_paths['raw_preschool_data_path'],
            processed_preschool_data_path=file_paths.get('processed_preschool_data_path')
        )

        # Run forecast
        forecaster = Forecaster(updated_config)
        results = forecaster.run()

        return {
            'existing_preschools': results[0],
            'forecasted_preschoolers': results[1],
            'forecasted_preschools_needed': results[2],
            'preschool_gap': results[3],
            'config': updated_config
        }

    except Exception as e:
        st.error(f"Error running forecast: {str(e)}")
        return None


def display_forecast_results():
    """Display the forecast results with interactive visualization."""
    results = st.session_state.forecast_results

    if not results:
        return

    # Get available forecast years
    forecast_years = list(results['forecasted_preschoolers'].index)

    # Year selection slider
    st.subheader("📅 Select Forecast Year")
    selected_year = st.select_slider(
        "Year",
        options=forecast_years,
        value=forecast_years[-1],  # Default to last year
        format_func=lambda x: str(x)
    )

    # Display summary statistics
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        total_preschoolers = results['forecasted_preschoolers'].loc[selected_year].sum()
        st.metric("Total Projected Preschoolers", f"{total_preschoolers:,.0f}")

    with col2:
        total_needed = results['forecasted_preschools_needed'].loc[selected_year].sum()
        st.metric("Total Preschools Needed", f"{total_needed:,.0f}")

    with col3:
        current_preschools = results['existing_preschools']['num_preschools'].sum()
        st.metric("Current Preschools", f"{current_preschools:,.0f}")

    with col4:
        total_gap = results['preschool_gap'].loc[selected_year].sum()
        gap_color = "inverse" if total_gap < 0 else "normal"
        st.metric("Overall Gap", f"{total_gap:,.0f}", delta_color=gap_color)

    # Create interactive map visualization
    st.subheader(f"📍 Geographic Analysis for {selected_year}")

    try:
        # Prepare mapping data for selected year
        map_data = prepare_mapping_data_merge(
            results['existing_preschools'],
            results['forecasted_preschoolers'],
            results['forecasted_preschools_needed'],
            results['preschool_gap'],
            year=selected_year
        )

        # Create tabs for different views
        tab1, tab2, tab3, tab4 = st.tabs([
            "Current Supply",
            "Projected Demand",
            "Preschools Needed",
            "Shortage Areas"
        ])

        with tab1:
            create_choropleth_map(map_data, 'num_preschools',
                                  'Current Preschools', 'Blues')

        with tab2:
            create_choropleth_map(map_data, 'projected_preschoolers',
                                  f'Projected Preschoolers ({selected_year})',
                                  'Oranges')

        with tab3:
            create_choropleth_map(map_data, 'preschools_needed',
                                  f'Preschools Needed ({selected_year})', 'Reds')

        with tab4:
            create_shortage_map(map_data, selected_year)

    except Exception as e:
        st.error(f"Error creating visualization: {str(e)}")
        st.info("Displaying data table instead:")
        st.dataframe(map_data.head())


def create_choropleth_map(map_data, column, title, colorscale):
    """Create a choropleth map using Folium."""
    try:
        st.subheader(title)
        
        # Check if we have geometry data
        if 'geometry' not in map_data.columns:
            st.warning("No geometry data available. Showing bar chart instead.")
            create_fallback_chart(map_data, column, title, colorscale)
            return
        
        # Reset index to get subzone names as a column if needed
        if map_data.index.name == 'subzone_name_clean':
            plot_data = map_data.reset_index()
        else:
            plot_data = map_data.copy()
        
        # Create folium map centered on Singapore
        singapore_center = [1.3521, 103.8198]
        m = folium.Map(location=singapore_center, zoom_start=11, tiles='OpenStreetMap')
        
        # Find the correct key for subzone names in GeoJSON properties
        if len(plot_data) > 0:
            first_feature = plot_data.__geo_interface__['features'][0] if plot_data.__geo_interface__['features'] else {}
            available_props = list(first_feature.get('properties', {}).keys())
            
            # Try to find the correct key for subzone names
            possible_keys = ['subzone_name_clean', 'subzone', 'SUBZONE_N', 'Name']
            key_to_use = None
            for key in possible_keys:
                if key in available_props:
                    key_to_use = key
                    break
            
            if key_to_use:
                # Add choropleth layer
                folium.Choropleth(
                    geo_data=plot_data.__geo_interface__,
                    name=title,
                    data=plot_data.reset_index(),
                    columns=['subzone_name_clean', column],
                    key_on=f'feature.properties.{key_to_use}',
                    fill_color=get_folium_colorscale(colorscale),
                    fill_opacity=0.7,
                    line_opacity=0.2,
                    legend_name=title
                ).add_to(m)
            else:
                # Fallback to manual styling
                def style_function(feature):
                    return {
                        'fillColor': 'blue',
                        'color': 'black',
                        'weight': 1,
                        'fillOpacity': 0.7
                    }
                
                folium.GeoJson(
                    plot_data.__geo_interface__,
                    style_function=style_function
                ).add_to(m)
        
        # Add tooltips
        folium.GeoJson(
            plot_data.__geo_interface__,
            style_function=lambda x: {
                'fillColor': 'transparent',
                'color': 'black',
                'weight': 1,
                'fillOpacity': 0
            },
            tooltip=folium.GeoJsonTooltip(
                fields=['subzone_name_clean', column],
                aliases=['Subzone:', f'{title}:'],
                localize=True
            )
        ).add_to(m)
        
        # Display the map
        st_folium(m, width=700, height=500)
        
        # Show summary statistics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total", f"{plot_data[column].sum():,.0f}")
        with col2:
            st.metric("Average", f"{plot_data[column].mean():.1f}")
        with col3:
            st.metric("Max", f"{plot_data[column].max():,.0f}")

    except Exception as e:
        st.error(f"Error creating map: {str(e)}")
        st.info("Falling back to bar chart:")
        create_fallback_chart(map_data, column, title, colorscale)


def create_fallback_chart(map_data, column, title, colorscale):
    """Create a fallback bar chart when map creation fails."""
    try:
        # Reset index to get subzone names as a column
        map_data_reset = map_data.reset_index()

        # Show top 10 subzones
        top_data = map_data_reset.nlargest(10, column)[['subzone_name_clean', column]]

        fig = px.bar(
            top_data,
            x=column,
            y='subzone_name_clean',
            orientation='h',
            title=f"Top 10 Subzones - {title}",
            color=column,
            color_continuous_scale=colorscale
        )

        fig.update_layout(height=400)
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error creating fallback chart: {str(e)}")


def get_folium_colorscale(plotly_colorscale):
    """Convert Plotly colorscale to Folium colorscale."""
    colorscale_map = {
        'Blues': 'Blues',
        'Oranges': 'Oranges', 
        'Reds': 'Reds',
        'Greens': 'Greens',
        'Purples': 'Purples',
        'YlOrRd': 'YlOrRd',
        'YlGnBu': 'YlGnBu'
    }
    return colorscale_map.get(plotly_colorscale, 'YlOrRd')


def create_shortage_map(map_data, year):
    """Create a map highlighting shortage areas."""
    try:
        st.subheader(f"Preschool Shortages - Priority Areas ({year})")

        # Filter to shortage areas only
        shortage_data = map_data[map_data['shortage'] > 0].copy()

        if len(shortage_data) > 0:
            # Check if we have geometry data for mapping
            if 'geometry' in map_data.columns:
                # Create map highlighting shortage areas
                singapore_center = [1.3521, 103.8198]
                m = folium.Map(location=singapore_center, zoom_start=11, tiles='OpenStreetMap')
                
                # Add base layer for all subzones (light gray)
                folium.GeoJson(
                    map_data.__geo_interface__,
                    style_function=lambda x: {
                        'fillColor': 'lightgray',
                        'color': 'white',
                        'weight': 1,
                        'fillOpacity': 0.3
                    }
                ).add_to(m)
                
                # Prepare shortage data for choropleth - ensure proper structure
                shortage_reset = shortage_data.reset_index()
                
                # Try choropleth approach first
                try:
                    # Find the correct key for subzone names in GeoJSON properties
                    if len(map_data) > 0:
                        first_feature = map_data.__geo_interface__['features'][0]
                        available_props = list(first_feature.get('properties', {}).keys())
                        
                        # Try to find the correct key for subzone names
                        possible_keys = ['subzone_name_clean', 'subzone', 'SUBZONE_N', 'Name']
                        key_to_use = None
                        for key in possible_keys:
                            if key in available_props:
                                key_to_use = key
                                break
                        
                        if key_to_use:
                            # Use choropleth with proper key mapping
                            folium.Choropleth(
                                geo_data=map_data.__geo_interface__,
                                name='Shortage Areas',
                                data=shortage_reset,
                                columns=['subzone_name_clean', 'shortage'],
                                key_on=f'feature.properties.{key_to_use}',
                                fill_color='Reds',
                                fill_opacity=0.8,
                                line_opacity=0.8,
                                line_color='darkred',
                                legend_name='Preschool Shortage',
                                nan_fill_color='lightgray',
                                nan_fill_opacity=0.3
                            ).add_to(m)
                        else:
                            raise Exception("No matching key found for choropleth")
                except Exception:
                    # Fallback: Manual styling of shortage areas
                    def style_function(feature):
                        subzone_name = feature.get('properties', {}).get('subzone_name_clean', '')
                        if subzone_name in shortage_reset['subzone_name_clean'].values:
                            shortage_val = shortage_reset[shortage_reset['subzone_name_clean'] == subzone_name]['shortage'].iloc[0]
                            # Scale color intensity based on shortage
                            intensity = min(1.0, shortage_val / shortage_reset['shortage'].max())
                            return {
                                'fillColor': f'rgba(255, {int(255*(1-intensity))}, {int(255*(1-intensity))}, 0.8)',
                                'color': 'darkred',
                                'weight': 2,
                                'fillOpacity': 0.8
                            }
                        return {
                            'fillColor': 'lightgray',
                            'color': 'white',
                            'weight': 1,
                            'fillOpacity': 0.3
                        }
                    
                    folium.GeoJson(
                        map_data.__geo_interface__,
                        style_function=style_function
                    ).add_to(m)
                
                # Add tooltips for shortage areas only
                def get_tooltip_data(feature):
                    subzone_name = feature.get('properties', {}).get('subzone_name_clean', '')
                    if subzone_name in shortage_reset['subzone_name_clean'].values:
                        shortage_val = shortage_reset[shortage_reset['subzone_name_clean'] == subzone_name]['shortage'].iloc[0]
                        return f"<b>{subzone_name}</b><br/>Shortage: {shortage_val:.0f} preschools"
                    return None
                
                for _, row in shortage_reset.iterrows():
                    if hasattr(row, 'geometry') and row.geometry is not None:
                        folium.GeoJson(
                            row.geometry.__geo_interface__,
                            tooltip=f"<b>{row['subzone_name_clean']}</b><br/>Shortage: {row['shortage']:.0f} preschools",
                            style_function=lambda x: {
                                'fillColor': 'transparent',
                                'color': 'darkred',
                                'weight': 2,
                                'fillOpacity': 0
                            }
                        ).add_to(m)
                
                # Display the map
                st_folium(m, width=700, height=500)
                
            else:
                # Fallback to bar chart
                shortage_reset = shortage_data.reset_index()
                fig = px.bar(
                    shortage_reset.nlargest(15, 'shortage'),
                    x='shortage',
                    y='subzone_name_clean',
                    orientation='h',
                    title="Subzones with Preschool Shortages (Priority Areas)",
                    color='shortage',
                    color_continuous_scale='Reds'
                )
                fig.update_layout(height=500)
                st.plotly_chart(fig, use_container_width=True)

            st.write(f"**{len(shortage_data)} subzones** have preschool shortages")
            st.write(f"**Total shortage**: {shortage_data['shortage'].sum():.0f} preschools")

        else:
            st.success("No preschool shortages projected for this year!")

    except Exception as e:
        st.error(f"Error creating shortage visualization: {str(e)}")
        st.info("Falling back to bar chart:")
        # Emergency fallback
        try:
            shortage_reset = shortage_data.reset_index()
            fig = px.bar(
                shortage_reset.nlargest(10, 'shortage'),
                x='shortage',
                y='subzone_name_clean',
                orientation='h',
                title="Top 10 Shortage Areas",
                color='shortage',
                color_continuous_scale='Reds'
            )
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
        except Exception as fallback_error:
            st.error(f"Fallback also failed: {fallback_error}")


if __name__ == "__main__":
    main()

