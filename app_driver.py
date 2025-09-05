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

# Przycisk do czyszczenia cache'a
if st.sidebar.button("🗑️ Wyczyść cache", help="Usuń załadowane dane z pamięci"):
    if 'cached_file_key' in st.session_state:
        del st.session_state.cached_file_key
    if 'cached_sheets_data' in st.session_state:
        del st.session_state.cached_sheets_data
    st.sidebar.success("✅ Cache wyczyszczony!")
    st.rerun()

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
        # Sprawdź czy plik jest już w cache
        file_key = f"{uploaded_file.name}_{uploaded_file.size}"
        
        if 'cached_file_key' not in st.session_state or st.session_state.cached_file_key != file_key:
            # Ładowanie danych
            with st.spinner("Ładowanie pliku..."):
                sheets_data = load_excel_file(uploaded_file)
            
            if sheets_data:
                st.success(f"✅ Plik załadowany pomyślnie! Znaleziono {len(sheets_data)} arkuszy.")
                # Zapisz w session state
                st.session_state.cached_file_key = file_key
                st.session_state.cached_sheets_data = sheets_data
            else:
                st.error("❌ Nie udało się załadować pliku.")
                sheets_data = None
        else:
            # Użyj danych z cache
            sheets_data = st.session_state.cached_sheets_data
            st.success(f"✅ Plik załadowany z cache! Znaleziono {len(sheets_data)} arkuszy.")
        
        if sheets_data:
            # Automatycznie wybierz pierwszy arkusz
            first_sheet = list(sheets_data.keys())[0]
            df = sheets_data[first_sheet]
            
            
            # Konwertuj daty i czas przed filtrowaniem
            for col in df.columns:
                if col.upper() == 'DATA' and pd.api.types.is_numeric_dtype(df[col]):
                    # Konwertuj daty Excel na prawidłowe daty
                    df[col] = pd.to_datetime('1900-01-01') + pd.to_timedelta(df[col] - 2, unit='D')
                elif col.upper() == 'TIME' and pd.api.types.is_numeric_dtype(df[col]):
                    # Konwertuj czas Excel na prawidłowy czas
                    df[col] = pd.to_datetime('1900-01-01') + pd.to_timedelta(df[col], unit='D')
                    df[col] = df[col].dt.time
            
            # Napraw problematyczne kolumny dla Streamlit
            problematic_columns = ['Street Num', 'Numer', 'Postal', 'Exception']
            for col in problematic_columns:
                if col in df.columns:
                    try:
                        # Konwertuj na string, żeby uniknąć błędów konwersji
                        df[col] = df[col].astype(str)
                    except Exception as e:
                        st.warning(f"⚠️ Nie udało się skonwertować kolumny {col}: {str(e)}")
            
            # Sprawdź czy istnieje kolumna "Driver ID:"
            if 'Driver ID:' in df.columns:
                # Kalendarz
                st.sidebar.markdown("---")
                st.sidebar.header("📅 Wybór dat")
                
                # Znajdź kolumnę z datami
                date_column = None
                for col in df.columns:
                    if col.upper() == 'DATA' or 'date' in col.lower():
                        date_column = col
                        break
                
                if date_column is not None:
                    try:
                        # Pobierz zakres dat z danych
                        min_date = df[date_column].min().date()
                        max_date = df[date_column].max().date()
                        
                        # Opcje wyboru dat
                        # Inicjalizuj session state dla zapamiętywania wyboru dat
                        if 'date_option' not in st.session_state:
                            st.session_state.date_option = "Wszystkie daty"
                        
                        # Przygotuj listę opcji dat
                        date_options = ["Wszystkie daty", "Tylko soboty", "Niestandardowy wybór"]
                        
                        # Znajdź indeks dla zapamiętanego wyboru
                        try:
                            date_index = date_options.index(st.session_state.date_option)
                        except ValueError:
                            date_index = 0
                        
                        date_option = st.sidebar.radio(
                            "Wybierz opcję dat:",
                            date_options,
                            index=date_index,
                            help="Wybór zostanie zapamiętany"
                        )
                        
                        # Zapisz wybór w session state
                        st.session_state.date_option = date_option
                        
                        if date_option == "Tylko soboty":
                            # Filtruj tylko soboty
                            df = df[df[date_column].dt.dayofweek == 5]  # 5 = sobota
                            st.sidebar.success(f"📅 Wyświetlane tylko soboty: {len(df)} wierszy")
                        elif date_option == "Niestandardowy wybór":
                            # Kalendarz z możliwością zaznaczenia dni
                            selected_dates = st.sidebar.date_input(
                                "Wybierz daty:",
                                value=(min_date, max_date),
                                min_value=min_date,
                                max_value=max_date,
                                help="Możesz wybrać pojedynczy dzień lub zakres dat"
                            )
                            
                            # Filtruj dane według wybranych dat
                            if isinstance(selected_dates, tuple) and len(selected_dates) == 2:
                                start_date, end_date = selected_dates
                                df = df[(df[date_column].dt.date >= start_date) & (df[date_column].dt.date <= end_date)]
                            elif selected_dates:
                                df = df[df[date_column].dt.date == selected_dates]
                                
                            st.sidebar.success(f"📅 Filtrowanie według dat: {len(df)} wierszy")
                        else:
                            st.sidebar.info("📅 Wyświetlane wszystkie daty")
                        
                    except Exception as e:
                        st.sidebar.error(f"❌ Błąd podczas przetwarzania dat: {str(e)}")
                else:
                    st.sidebar.warning("⚠️ Nie znaleziono kolumny z datami")
                
                # Wybór driver id
                st.sidebar.markdown("---")
                st.sidebar.header("🚗 Wybór Driver ID")
                unique_drivers = df['Driver ID:'].dropna().unique()
                
                # Inicjalizuj session state dla zapamiętywania wyboru Driver ID
                if 'selected_driver' not in st.session_state:
                    st.session_state.selected_driver = 'Wszyscy'
                
                # Sprawdź czy poprzedni wybór jest nadal dostępny
                if st.session_state.selected_driver not in ['Wszyscy'] + list(unique_drivers):
                    st.session_state.selected_driver = 'Wszyscy'
                
                # Przygotuj listę opcji
                driver_options = ['Wszyscy'] + list(unique_drivers)
                
                # Znajdź indeks dla zapamiętanego wyboru
                try:
                    default_index = driver_options.index(st.session_state.selected_driver)
                except ValueError:
                    default_index = 0
                
                selected_driver = st.sidebar.selectbox(
                    "Wybierz Driver ID:",
                    options=driver_options,
                    index=default_index,
                    help="Wybór zostanie zapamiętany"
                )
                
                # Zapisz wybór w session state
                st.session_state.selected_driver = selected_driver
                
                # Filtruj dane według wybranego driver id
                if selected_driver != 'Wszyscy':
                    df = df[df['Driver ID:'] == selected_driver]
                    st.info(f"📊 Wyświetlane dane dla Driver ID: {selected_driver}")
                else:
                    st.info("📊 Wyświetlane dane dla wszystkich kierowców")
                
                # Wybór Exception Info
                st.sidebar.markdown("---")
                st.sidebar.header("⚠️ Exception info")
                
                # Sprawdź czy istnieje kolumna Exception Info
                if 'Exception info' in df.columns:
                    # Zahardkodowane wartości do wyboru
                    hardcoded_exceptions = ["DR RELEASED", "COMM INS REL", "SIG OBTAINED"]
                    
                    # Sprawdź które z zahardkodowanych wartości są dostępne w danych
                    available_hardcoded = [exc for exc in hardcoded_exceptions if exc in df['Exception info'].values]
                    
                    if available_hardcoded:
                        # Inicjalizuj session state dla zapamiętywania wyboru - zawsze wszystkie dostępne wartości
                        if 'selected_exceptions' not in st.session_state:
                            st.session_state.selected_exceptions = available_hardcoded
                        
                        # Sprawdź czy poprzednie wybory są nadal dostępne
                        available_exceptions = [exc for exc in st.session_state.selected_exceptions if exc in available_hardcoded]
                        
                        selected_exceptions = st.sidebar.multiselect(
                            "Wybierz wartości Exception info:",
                            options=available_hardcoded,
                            default=available_hardcoded,  # Zawsze wszystkie zaznaczone domyślnie
                            help="Wszystkie wartości są domyślnie zaznaczone. Możesz odznaczyć niektóre."
                        )
                        
                        # Zapisz wybór w session state
                        st.session_state.selected_exceptions = selected_exceptions
                        
                        if selected_exceptions:
                            # Filtruj dane według wybranych wartości
                            df = df[df['Exception info'].isin(selected_exceptions)]
                            st.info(f"⚠️ Wyświetlane wiersze z Exception info: {', '.join(selected_exceptions)}")
                            
                        else:
                            st.info("⚠️ Wyświetlane wszystkie wiersze")
                    else:
                        st.sidebar.warning("⚠️ Brak zahardkodowanych wartości w kolumnie Exception info")
                        st.sidebar.info(f"💡 Dostępne wartości: {', '.join(df['Exception info'].dropna().unique()[:5])}...")
                else:
                    st.sidebar.warning("⚠️ Nie znaleziono kolumny 'Exception info'")
            else:
                st.warning("⚠️ Nie znaleziono kolumny 'Driver ID:' w danych")
                st.info("📊 Wyświetlane wszystkie dane")
                selected_driver = 'Wszyscy'
            
            # Informacje o danych
            st.sidebar.markdown("---")
            st.sidebar.header("ℹ️ Informacje o danych")
            st.sidebar.metric("Liczba wierszy", len(df))
            st.sidebar.metric("Liczba kolumn", len(df.columns))
            
                    # Wyświetl statystyki Exception info i City Name nad Driver ID
        if 'Exception info' in df.columns:
            exception_counts = df['Exception info'].value_counts()
            total_exceptions = len(df[df['Exception info'].notna() & (df['Exception info'] != '')])

            col1, col2, col3 = st.columns([2, 2, 1])

            with col1:
                st.metric("Exception info (filtrowane)", total_exceptions)
                if len(exception_counts) > 0:
                    st.caption(f"Top: {exception_counts.index[0]} ({exception_counts.iloc[0]})")

            with col2:
                # Statystyki City Name - liczenie unikalnych adresów z datą
                if 'City Name' in df.columns:
                    # Sprawdź czy wszystkie wymagane kolumny adresowe istnieją
                    address_columns = ['Postal', 'City Name', 'Street Name', 'Street Num']
                    available_address_columns = [col for col in address_columns if col in df.columns]
                    
                    # Znajdź kolumnę z datą
                    date_column = None
                    for col in df.columns:
                        if col.upper() == 'DATA' or 'date' in col.lower():
                            date_column = col
                            break
                    
                    if len(available_address_columns) >= 2:  # Minimum City Name + jedna inna kolumna adresowa
                        # Utwórz unikalne kombinacje adresów + data
                        if date_column and len(available_address_columns) == 4:
                            # Wszystkie kolumny adresowe + data dostępne
                            unique_columns = address_columns + [date_column]
                            unique_addresses = df[unique_columns].drop_duplicates()
                        elif date_column:
                            # Tylko dostępne kolumny + data
                            unique_columns = available_address_columns + [date_column]
                            unique_addresses = df[unique_columns].drop_duplicates()
                        elif len(available_address_columns) == 4:
                            # Wszystkie kolumny adresowe bez daty
                            unique_addresses = df[address_columns].drop_duplicates()
                        else:
                            # Tylko dostępne kolumny bez daty
                            unique_addresses = df[available_address_columns].drop_duplicates()
                        
                        # Policz miasta w unikalnych adresach
                        city_counts = unique_addresses['City Name'].value_counts()
                        wroclaw_count = city_counts.get('WROCLAW', 0)
                        other_count = len(unique_addresses) - wroclaw_count
                        
                        st.metric("WROCLAW (unikalne adresy)", wroclaw_count)
                        st.metric("Inne miasta (unikalne adresy)", other_count)
                        if date_column:
                            st.caption(f"Łącznie unikalnych adresów z datą: {len(unique_addresses)}")
                        else:
                            st.caption(f"Łącznie unikalnych adresów: {len(unique_addresses)}")
                    else:
                        # Fallback - liczenie bezpośrednio z City Name
                        city_counts = df['City Name'].value_counts()
                        wroclaw_count = city_counts.get('WROCLAW', 0)
                        other_count = len(df) - wroclaw_count
                        
                        st.metric("WROCLAW", wroclaw_count)
                        st.metric("Inne miasta", other_count)
                        st.caption("⚠️ Brak pełnych danych adresowych")
                else:
                    st.info("Brak kolumny 'City Name'")

            with col3:
                st.empty()  # Pusty placeholder
            
            # Główna zawartość
            col1, col2 = st.columns([3, 1])
            
            with col1:
                if 'Driver ID:' in df.columns and selected_driver != 'Wszyscy':
                    st.header(f"📊 Driver ID: {selected_driver}")
                else:
                    st.header("📊 Wszystkie dane")
                
                # Podgląd danych
                st.subheader("Podgląd danych")
                st.dataframe(df.head(10), width='stretch')
                
            
            with col2:
                st.header("💾 Eksport")
                
                # Eksport danych
                if st.button("Pobierz dane (CSV)"):
                    csv = df.to_csv(index=False)
                    st.download_button(
                        label="📥 Pobierz CSV",
                        data=csv,
                        file_name=f"dane_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                        mime="text/csv"
                    )
                
                if st.button("Pobierz dane (Excel)"):
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df.to_excel(writer, sheet_name='Dane', index=False)
                    output.seek(0)
                    
                    st.download_button(
                        label="📥 Pobierz Excel",
                        data=output.getvalue(),
                        file_name=f"dane_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            
            # Wyświetl dane
            st.markdown("---")
            st.subheader("📋 Dane")
            st.dataframe(df, width='stretch')

else:
    # Instrukcje gdy nie ma pliku
    st.info("👆 Załaduj plik Excel, aby rozpocząć przetwarzanie danych.")
    
    st.markdown("""
    ## 🚀 Funkcje aplikacji:
    
    - **📁 Ładowanie plików Excel** - obsługa formatów .xlsx, .xls i .xlsb
    - **📅 Wybór dat** - kalendarz z opcjami: wszystkie daty, tylko soboty, niestandardowy wybór (zapamiętuje wybór)
    - **🚗 Wybór Driver ID** - filtrowanie danych według kierowcy (zapamiętuje wybór)
    - **⚠️ Exception info** - multiselect z zahardkodowanymi wartościami: DR RELEASED, COMM INS REL, SIG OBTAINED
    - **📊 Podgląd danych** - wyświetlanie pierwszych 10 wierszy
    - **💾 Eksport** - pobieranie danych w formacie CSV lub Excel
    
    ## 📝 Jak używać:
    1. Załaduj plik Excel używając przycisku w lewym panelu
    2. Wybierz opcję dat (wszystkie, tylko soboty, lub niestandardowy wybór) - wybór zostanie zapamiętany
    3. Wybierz Driver ID z listy rozwijanej - wybór zostanie zapamiętany
    4. Wybierz z zahardkodowanych wartości Exception info: DR RELEASED, COMM INS REL, SIG OBTAINED
    5. Przejrzyj dane
    6. Eksportuj wyniki w formacie CSV lub Excel
    """)

# Stopka
st.markdown("---")
st.markdown("💡 **Wskazówka:** Aplikacja automatycznie cache'uje załadowane pliki dla lepszej wydajności.")
