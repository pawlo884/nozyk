import streamlit as st
import pandas as pd
import io
from datetime import datetime
import pyxlsb

# Konfiguracja strony
st.set_page_config(
    page_title="Przetwarzanie plików Excel",
    page_icon="📊",
    layout="wide"
)

# Tytuł aplikacji
st.title("📊 Aplikacja do przetwarzania plików Excel")
st.markdown("---")


# Funkcja do ładowania pliku Excel
@st.cache_data
def load_excel_file(file):
    """Ładuje plik Excel i zwraca słownik z arkuszami"""
    try:
        # Sprawdź rozszerzenie pliku
        file_extension = file.name.split('.')[-1].lower()
        
        if file_extension == 'xlsb':
            # Obsługa plików .xlsb
            sheets_dict = {}
            with pyxlsb.open_workbook(file) as wb:
                for sheet_name in wb.sheets:
                    dataframe = pd.read_excel(file, sheet_name=sheet_name, engine='pyxlsb')
                    sheets_dict[sheet_name] = dataframe
            return sheets_dict
        else:
            # Obsługa plików .xlsx i .xls
            excel_file = pd.ExcelFile(file)
            sheets_dict = {}
            
            for sheet_name in excel_file.sheet_names:
                dataframe = pd.read_excel(file, sheet_name=sheet_name)
                sheets_dict[sheet_name] = dataframe
                
            return sheets_dict
    except (ValueError, FileNotFoundError, PermissionError) as e:
        st.error(f"Błąd podczas ładowania pliku: {str(e)}")
        return None


# Sidebar - ładowanie pliku
st.sidebar.header("📁 Ładowanie pliku")
uploaded_file = st.sidebar.file_uploader(
    "Wybierz plik Excel",
    type=None,  # Pozwól na wszystkie typy plików
    accept_multiple_files=False,
    help="Obsługiwane formaty: .xlsx, .xls, .xlsb"
)

if uploaded_file is not None:
    # Sprawdź rozszerzenie pliku
    file_extension = uploaded_file.name.split('.')[-1].lower()
    if file_extension not in ['xlsx', 'xls', 'xlsb']:
        st.error(f"❌ Nieobsługiwany format pliku: .{file_extension}. Obsługiwane formaty: .xlsx, .xls, .xlsb")
    else:
        # Ładowanie danych
        with st.spinner("Ładowanie pliku..."):
            sheets_data = load_excel_file(uploaded_file)
        
        if sheets_data:
            st.success(f"✅ Plik załadowany pomyślnie! Znaleziono {len(sheets_data)} arkuszy.")
            
            # Automatycznie wybierz pierwszy arkusz
            first_sheet = list(sheets_data.keys())[0]
            df = sheets_data[first_sheet]
            
            # Sprawdź czy istnieje kolumna "driver id"
            if 'Driver ID:' in df.columns:
                # Wybór driver id
                st.sidebar.markdown("---")
                st.sidebar.header("🚗 Wybór Driver ID")
                unique_drivers = df['Driver ID:'].dropna().unique()
                selected_driver = st.sidebar.selectbox(
                    "Wybierz Driver ID:",
                    options=['Wszyscy'] + list(unique_drivers)
                )
                
                # Filtruj dane według wybranego driver id
                if selected_driver != 'Wszyscy':
                    df = df[df['Driver ID:'] == selected_driver]
                    st.info(f"📊 Wyświetlane dane dla Driver ID: {selected_driver}")
                else:
                    st.info("📊 Wyświetlane dane dla wszystkich kierowców")
            else:
                st.warning("⚠️ Nie znaleziono kolumny 'Driver ID:' w danych")
                st.info("📊 Wyświetlane wszystkie dane")
                selected_driver = 'Wszyscy'
            
            # Informacje o danych
            st.sidebar.markdown("---")
            st.sidebar.header("ℹ️ Informacje o danych")
            st.sidebar.metric("Liczba wierszy", len(df))
            st.sidebar.metric("Liczba kolumn", len(df.columns))
            
            # Główna zawartość
            col1, col2 = st.columns([2, 1])
            
            with col1:
                if 'Driver ID:' in df.columns and selected_driver != 'Wszyscy':
                    st.header(f"📊 Driver ID: {selected_driver}")
                else:
                    st.header("📊 Wszystkie dane")
                
                # Podgląd danych
                st.subheader("Podgląd danych")
                st.dataframe(df.head(10), use_container_width=True)
                
                # Statystyki opisowe
                st.subheader("📈 Statystyki opisowe")
                numeric_columns = df.select_dtypes(include=['number']).columns
                if len(numeric_columns) > 0:
                    st.dataframe(df[numeric_columns].describe(), use_container_width=True)
                else:
                    st.info("Brak kolumn numerycznych do analizy statystycznej.")
            
            with col2:
                st.header("🔧 Narzędzia")
                
                # Filtrowanie
                st.subheader("🔍 Filtrowanie")
                
                # Filtry dla każdej kolumny
                filtered_df = df.copy()
                
                for column in df.columns:
                    if df[column].dtype == 'object':  # Kolumny tekstowe
                        unique_values = df[column].dropna().unique()
                        if len(unique_values) <= 20:  # Tylko dla kolumn z małą liczbą unikalnych wartości
                            selected_values = st.multiselect(
                                f"Filtruj {column}:",
                                options=unique_values,
                                default=unique_values
                            )
                            if selected_values:
                                filtered_df = filtered_df[filtered_df[column].isin(selected_values)]
                    
                    elif pd.api.types.is_numeric_dtype(df[column]):  # Kolumny numeryczne
                        min_val = float(df[column].min())
                        max_val = float(df[column].max())
                        
                        range_values = st.slider(
                            f"Zakres {column}:",
                            min_value=min_val,
                            max_value=max_val,
                            value=(min_val, max_val),
                            step=0.01 if max_val - min_val < 1 else 1
                        )
                        filtered_df = filtered_df[
                            (filtered_df[column] >= range_values[0]) & 
                            (filtered_df[column] <= range_values[1])
                        ]
                
                # Wyniki filtrowania
                st.metric("Wiersze po filtrowaniu", len(filtered_df))
                
                # Eksport przefiltrowanych danych
                st.subheader("💾 Eksport")
                
                if st.button("Pobierz przefiltrowane dane (CSV)"):
                    csv = filtered_df.to_csv(index=False)
                    st.download_button(
                        label="📥 Pobierz CSV",
                        data=csv,
                        file_name=f"przefiltrowane_dane_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
                
                if st.button("Pobierz przefiltrowane dane (Excel)"):
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        filtered_df.to_excel(writer, sheet_name='Przefiltrowane', index=False)
                    output.seek(0)
                    
                    st.download_button(
                        label="📥 Pobierz Excel",
                        data=output.getvalue(),
                        file_name=f"przefiltrowane_dane_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            
            # Wyświetl przefiltrowane dane
            st.markdown("---")
            st.subheader("📋 Przefiltrowane dane")
            st.dataframe(filtered_df, use_container_width=True)
            
            # Dodatkowe narzędzia
            st.markdown("---")
            st.subheader("🛠️ Dodatkowe narzędzia")
            
            col3, col4, col5 = st.columns(3)
            
            with col3:
                # Grupowanie
                st.write("**Grupowanie**")
                group_column = st.selectbox("Grupuj według:", ["Brak"] + list(df.columns))
                if group_column != "Brak":
                    agg_column = st.selectbox("Agreguj kolumnę:", [col for col in df.columns if col != group_column])
                    if agg_column:
                        grouped = filtered_df.groupby(group_column)[agg_column].agg(['count', 'mean', 'sum']).round(2)
                        st.dataframe(grouped)
            
            with col4:
                # Sortowanie
                st.write("**Sortowanie**")
                sort_column = st.selectbox("Sortuj według:", ["Brak"] + list(df.columns))
                if sort_column != "Brak":
                    ascending = st.checkbox("Rosnąco", value=True)
                    sorted_df = filtered_df.sort_values(by=sort_column, ascending=ascending)
                    st.dataframe(sorted_df.head(10))
            
            with col5:
                # Wyszukiwanie
                st.write("**Wyszukiwanie**")
                search_term = st.text_input("Szukaj w danych:")
                if search_term:
                    # Wyszukaj we wszystkich kolumnach tekstowych
                    mask = pd.Series([False] * len(filtered_df))
                    for col in filtered_df.select_dtypes(include=['object']).columns:
                        mask |= filtered_df[col].astype(str).str.contains(search_term, case=False, na=False)
                    search_results = filtered_df[mask]
                    st.dataframe(search_results)

else:
    # Instrukcje gdy nie ma pliku
    st.info("👆 Załaduj plik Excel, aby rozpocząć przetwarzanie danych.")
    
    st.markdown("""
    ## 🚀 Funkcje aplikacji:
    
    - **📁 Ładowanie plików Excel** - obsługa formatów .xlsx, .xls i .xlsb
    - **🚗 Wybór Driver ID** - filtrowanie danych według kierowcy
    - **📊 Podgląd danych** - wyświetlanie pierwszych 10 wierszy
    - **📈 Statystyki** - podstawowe statystyki opisowe dla kolumn numerycznych
    - **🔍 Filtrowanie** - zaawansowane filtry dla kolumn tekstowych i numerycznych
    - **💾 Eksport** - pobieranie przefiltrowanych danych w formacie CSV lub Excel
    - **🛠️ Narzędzia** - grupowanie, sortowanie i wyszukiwanie w danych
    
    ## 📝 Jak używać:
    1. Załaduj plik Excel używając przycisku w lewym panelu
    2. Wybierz Driver ID z listy rozwijanej
    3. Użyj filtrów w prawym panelu, aby zawęzić dane
    4. Eksportuj wyniki lub użyj dodatkowych narzędzi
    """)

# Stopka
st.markdown("---")
st.markdown("💡 **Wskazówka:** Aplikacja automatycznie cache'uje załadowane pliki dla lepszej wydajności.")
