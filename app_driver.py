import streamlit as st
import pandas as pd
import io
from datetime import datetime
import pyxlsb
import folium
from streamlit_folium import st_folium

# Konfiguracja strony
st.set_page_config(
    page_title="Przetwarzanie plików Excel",
    page_icon="📊",
    layout="wide"
)

# Tytuł aplikacji
st.title("📊 :dagger: Nożyk App :dagger:")


st.markdown("---")


def fix_problematic_columns(df):
    """Naprawia problematyczne kolumny w DataFrame"""
    # Lista znanych problematycznych kolumn
    problematic_columns = ['Street Num', 'Numer', 'Postal', 'Exception',
                           'OPLD Consignee Name', 'Consignee Name', 'Consignee']

    # Sprawdź wszystkie kolumny pod kątem mieszanych typów
    for col in df.columns:
        try:
            # Sprawdź czy kolumna ma mieszane typy danych
            if df[col].dtype == 'object':
                # Sprawdź czy są różne typy w kolumnie
                non_null_values = df[col].dropna()
                if len(non_null_values) > 0:
                    types_in_col = non_null_values.apply(type).unique()
                    if len(types_in_col) > 1:
                        # Konwertuj wszystko na string
                        df[col] = df[col].astype(str)
        except Exception:
            # Jeśli nie można sprawdzić typów, po prostu konwertuj na string
            try:
                df[col] = df[col].astype(str)
            except Exception:
                pass

    # Konwertuj znane problematyczne kolumny
    for col in problematic_columns:
        if col in df.columns:
            try:
                df[col] = df[col].astype(str)
            except Exception:
                pass

    return df


def extract_driver_name(driver_id):
    """Wyciąga część nazwy Driver ID od 6 do 8 znaku"""
    driver_str = str(driver_id)
    if len(driver_str) >= 8:
        return driver_str[5:8]  # od 6 do 8 znaku (indeksy 5-7)
    elif len(driver_str) >= 5:
        return driver_str[5:]   # od 6 znaku do końca
    else:
        return driver_str       # cała nazwa jeśli krótsza niż 5 znaków


def create_gps_map(df):
    """Tworzy mapę z punktami GPS na podstawie kolumn GPSX i GPSY"""
    # Sprawdź czy istnieją kolumny GPS
    if 'GPSX' not in df.columns or 'GPSY' not in df.columns:
        return None

    # Filtruj dane z prawidłowymi współrzędnymi GPS
    gps_data = df[(df['GPSX'].notna()) & (df['GPSY'].notna()) &
                  (df['GPSX'] != '') & (df['GPSY'] != '')]

    if len(gps_data) == 0:
        return None

    # Konwertuj współrzędne na liczby
    try:
        gps_data = gps_data.copy()
        gps_data['GPSX'] = pd.to_numeric(gps_data['GPSX'], errors='coerce')
        gps_data['GPSY'] = pd.to_numeric(gps_data['GPSY'], errors='coerce')

        # Usuń wiersze z nieprawidłowymi współrzędnymi
        gps_data = gps_data.dropna(subset=['GPSX', 'GPSY'])

        if len(gps_data) == 0:
            return None

    except Exception as e:
        st.warning(f"⚠️ Błąd podczas konwersji współrzędnych GPS: {str(e)}")
        return None

    # Sprawdź czy współrzędne wyglądają jak UTM (duże liczby) czy geograficzne (małe liczby)
    sample_x = gps_data['GPSX'].iloc[0] if len(gps_data) > 0 else 0
    sample_y = gps_data['GPSY'].iloc[0] if len(gps_data) > 0 else 0

    # Sprawdź czy GPSX to szerokość (latitude) czy długość (longitude)
    # Jeśli GPSX jest w zakresie 49-55, to prawdopodobnie to jest latitude (szerokość)
    # Jeśli GPSX jest w zakresie 14-24, to prawdopodobnie to jest longitude (długość)
    is_gpsx_latitude = (sample_x >= 49 and sample_x <= 55)
    is_gpsx_longitude = (sample_x >= 14 and sample_x <= 24)

    # Jeśli współrzędne są duże (prawdopodobnie UTM), skonwertuj je
    if abs(sample_x) > 180 or abs(sample_y) > 90:
        st.info("🔄 Wykryto współrzędne UTM - konwertuję na współrzędne geograficzne...")

        # Konwersja UTM na geograficzne (przybliżona dla Polski)
        # Użyj przybliżonej konwersji UTM (bez pyproj dla kompatybilności z Streamlit Cloud)
        st.info("🔄 Używam przybliżonej konwersji UTM → geograficzne")

        # Przybliżona konwersja dla Polski (UTM Zone 33N)
        # To jest przybliżone, ale wystarczające dla większości przypadków w Polsce
        # Przybliżenie dla Polski
        gps_data['longitude'] = (gps_data['GPSX'] - 500000) / 111320 + 15.0
        # Przybliżenie dla Polski
        gps_data['latitude'] = (gps_data['GPSY'] - 5000000) / 110540 + 52.0

    else:
        # Współrzędne już są geograficzne - sprawdź kolejność
        if is_gpsx_latitude:
            # GPSX to latitude (szerokość), GPSY to longitude (długość)
            st.info(
                "🔍 Wykryto: GPSX = szerokość geograficzna, GPSY = długość geograficzna")
            gps_data['latitude'] = gps_data['GPSX']
            gps_data['longitude'] = gps_data['GPSY']
        elif is_gpsx_longitude:
            # GPSX to longitude (długość), GPSY to latitude (szerokość)
            st.info(
                "🔍 Wykryto: GPSX = długość geograficzna, GPSY = szerokość geograficzna")
            gps_data['longitude'] = gps_data['GPSX']
            gps_data['latitude'] = gps_data['GPSY']
        else:
            # Nie można określić - użyj domyślnej kolejności
            st.warning(
                "⚠️ Nie można określić kolejności współrzędnych - używam domyślnej kolejności")
            gps_data['longitude'] = gps_data['GPSX']
            gps_data['latitude'] = gps_data['GPSY']

    # Sprawdź czy współrzędne są w rozsądnym zakresie dla Polski
    valid_coords = gps_data[
        (gps_data['longitude'] >= 14) & (gps_data['longitude'] <= 24) &
        (gps_data['latitude'] >= 49) & (gps_data['latitude'] <= 55)
    ]

    if len(valid_coords) == 0:
        st.warning(
            "⚠️ Współrzędne nie wyglądają na polskie - sprawdź format danych")
        # Użyj oryginalnych współrzędnych jako fallback
        gps_data['longitude'] = gps_data['GPSX']
        gps_data['latitude'] = gps_data['GPSY']
    else:
        gps_data = valid_coords

    # Oblicz centrum mapy
    center_lat = gps_data['latitude'].mean()
    center_lon = gps_data['longitude'].mean()

    # Utwórz mapę
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=10,
        tiles='OpenStreetMap'
    )

    # Dodaj punkty na mapę
    for idx, row in gps_data.iterrows():
        # Przygotuj popup z informacjami
        popup_text = f"""
        <b>Numer monitorowania:</b> {row.get('Numer', 'Brak')}<br>
        <b>Driver ID:</b> {row.get('Driver ID:', 'Brak')}<br>
        <b>Data:</b> {row.get('DATA', 'Brak')}<br>
        <b>Miasto:</b> {row.get('City Name', 'Brak')}<br>
        <b>Exception info:</b> {row.get('Exception info', 'Brak')}<br>
        <b>Współrzędne:</b> {row['latitude']:.6f}, {row['longitude']:.6f}
        """

        # Kolor punktu na podstawie Exception info
        color = 'red'  # domyślnie czerwony
        if 'Exception info' in row and pd.notna(row['Exception info']):
            if 'DR RELEASED' in str(row['Exception info']):
                color = 'green'
            elif 'COMM INS REL' in str(row['Exception info']):
                color = 'blue'
            elif 'SIG OBTAINED' in str(row['Exception info']):
                color = 'orange'

        # Dodaj marker
        folium.CircleMarker(
            location=[row['latitude'], row['longitude']],
            radius=6,
            popup=folium.Popup(popup_text, max_width=300),
            color='black',
            weight=1,
            fillColor=color,
            fillOpacity=0.7
        ).add_to(m)

    return m


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
                    try:
                        dataframe = pd.read_excel(
                            file, sheet_name=sheet_name, engine='pyxlsb')
                        # Napraw problematyczne kolumny
                        dataframe = fix_problematic_columns(dataframe)
                        sheets_dict[sheet_name] = dataframe
                    except Exception as e:
                        st.warning(
                            f"⚠️ Problem z arkuszem {sheet_name}: {str(e)}")
                        # Spróbuj załadować z domyślnymi ustawieniami
                        try:
                            dataframe = pd.read_excel(
                                file, sheet_name=sheet_name, engine='pyxlsb', dtype=str)
                            sheets_dict[sheet_name] = dataframe
                        except Exception:
                            st.error(
                                f"❌ Nie udało się załadować arkusza {sheet_name}")
            return sheets_dict
        else:
            # Obsługa plików .xlsx i .xls
            excel_file = pd.ExcelFile(file)
            sheets_dict = {}

            for sheet_name in excel_file.sheet_names:
                try:
                    dataframe = pd.read_excel(file, sheet_name=sheet_name)
                    # Napraw problematyczne kolumny
                    dataframe = fix_problematic_columns(dataframe)
                    sheets_dict[sheet_name] = dataframe
                except Exception as e:
                    st.warning(f"⚠️ Problem z arkuszem {sheet_name}: {str(e)}")
                    # Spróbuj załadować z domyślnymi ustawieniami
                    try:
                        dataframe = pd.read_excel(
                            file, sheet_name=sheet_name, dtype=str)
                        sheets_dict[sheet_name] = dataframe
                    except Exception:
                        st.error(
                            f"❌ Nie udało się załadować arkusza {sheet_name}")

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

    # Wyczyść wszystkie mapy GPS (stare i nowe)
    keys_to_remove = []
    for key in st.session_state.keys():
        if key.startswith('gps_map_') or key.startswith('gps_loaded_'):
            keys_to_remove.append(key)

    for key in keys_to_remove:
        del st.session_state[key]

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
        st.error(
            f"❌ Nieobsługiwany format pliku: .{file_extension}. Obsługiwane formaty: .xlsx, .xls, .xlsb")
    else:
        # Sprawdź czy plik jest już w cache
        file_key = f"{uploaded_file.name}_{uploaded_file.size}"

        if 'cached_file_key' not in st.session_state or st.session_state.cached_file_key != file_key:
            # Ładowanie danych
            with st.spinner("Ładowanie pliku..."):
                sheets_data = load_excel_file(uploaded_file)

            if sheets_data:
                st.success(
                    f"✅ Plik załadowany pomyślnie! Znaleziono {len(sheets_data)} arkuszy.")
                # Zapisz w session state
                st.session_state.cached_file_key = file_key
                st.session_state.cached_sheets_data = sheets_data
            else:
                st.error("❌ Nie udało się załadować pliku.")
                sheets_data = None
        else:
            # Użyj danych z cache
            sheets_data = st.session_state.cached_sheets_data
            st.success(
                f"✅ Plik załadowany z cache! Znaleziono {len(sheets_data)} arkuszy.")

        if sheets_data:
            # Automatycznie wybierz pierwszy arkusz
            first_sheet = list(sheets_data.keys())[0]
            df = sheets_data[first_sheet]

            # Konwertuj daty i czas przed filtrowaniem
            for col in df.columns:
                if col.upper() == 'DATA' and pd.api.types.is_numeric_dtype(df[col]):
                    # Konwertuj daty Excel na prawidłowe daty
                    df[col] = pd.to_datetime(
                        '1900-01-01') + pd.to_timedelta(df[col] - 2, unit='D')
                elif col.upper() == 'TIME' and pd.api.types.is_numeric_dtype(df[col]):
                    # Konwertuj czas Excel na prawidłowy czas
                    df[col] = pd.to_datetime(
                        '1900-01-01') + pd.to_timedelta(df[col], unit='D')
                    df[col] = df[col].dt.time

            # Napraw problematyczne kolumny dla Streamlit (dodatkowa naprawa)
            df = fix_problematic_columns(df)

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
                        date_options = ["Wszystkie daty",
                                        "Tylko soboty", "Niestandardowy wybór"]

                        # Znajdź indeks dla zapamiętanego wyboru
                        try:
                            date_index = date_options.index(
                                st.session_state.date_option)
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
                            # 5 = sobota
                            df = df[df[date_column].dt.dayofweek == 5]
                            st.sidebar.success(
                                f"📅 Wyświetlane tylko soboty: {len(df)} wierszy")
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
                                df = df[(df[date_column].dt.date >= start_date) & (
                                    df[date_column].dt.date <= end_date)]
                            elif selected_dates:
                                df = df[df[date_column].dt.date ==
                                        selected_dates]

                            st.sidebar.success(
                                f"📅 Filtrowanie według dat: {len(df)} wierszy")
                        else:
                            st.sidebar.info("📅 Wyświetlane wszystkie daty")

                    except Exception as e:
                        st.sidebar.error(
                            f"❌ Błąd podczas przetwarzania dat: {str(e)}")
                else:
                    st.sidebar.warning("⚠️ Nie znaleziono kolumny z datami")

                # Wybór driver id
                st.sidebar.markdown("---")
                st.sidebar.header("🚗 Wybór Driver ID")
                unique_drivers = df['Driver ID:'].dropna().unique()

                # Wyciągnij część nazwy od 5 do 8 znaku dla lepszej czytelności
                # Stwórz mapowanie oryginalnych nazw na skrócone
                driver_mapping = {}
                for driver_id in unique_drivers:
                    short_name = extract_driver_name(driver_id)
                    driver_mapping[short_name] = driver_id

                # Inicjalizuj session state dla zapamiętywania wyboru Driver ID
                if 'selected_driver' not in st.session_state:
                    st.session_state.selected_driver = 'Wszyscy'

                # Sprawdź czy poprzedni wybór jest nadal dostępny
                if st.session_state.selected_driver not in ['Wszyscy'] + list(driver_mapping.keys()):
                    st.session_state.selected_driver = 'Wszyscy'

                # Przygotuj listę opcji - posortuj skrócone nazwy Driver ID alfabetycznie
                sorted_drivers = sorted(driver_mapping.keys())

                driver_options = ['Wszyscy'] + list(sorted_drivers)

                # Znajdź indeks dla zapamiętanego wyboru
                try:
                    default_index = driver_options.index(
                        st.session_state.selected_driver)
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
                    # Użyj oryginalnej nazwy Driver ID do filtrowania
                    original_driver_id = driver_mapping[selected_driver]
                    df = df[df['Driver ID:'] == original_driver_id]
                    st.info(
                        f"📊 Wyświetlane dane dla Driver ID: {original_driver_id} (skrócone: {selected_driver})")
                else:
                    st.info("📊 Wyświetlane dane dla wszystkich kierowców")

                # Wybór Exception Info
                st.sidebar.markdown("---")
                st.sidebar.header("⚠️ Exception info")

                # Sprawdź czy istnieje kolumna Exception Info
                if 'Exception info' in df.columns:
                    # Zahardkodowane wartości do wyboru
                    hardcoded_exceptions = [
                        "DR RELEASED", "COMM INS REL", "SIG OBTAINED"]

                    # Sprawdź które z zahardkodowanych wartości są dostępne w danych
                    available_hardcoded = [
                        exc for exc in hardcoded_exceptions
                        if exc in df['Exception info'].values]

                    if available_hardcoded:
                        # Inicjalizuj session state dla zapamiętywania wyboru - zawsze wszystkie dostępne wartości
                        if 'selected_exceptions' not in st.session_state:
                            st.session_state.selected_exceptions = available_hardcoded

                        # Sprawdź czy poprzednie wybory są nadal dostępne
                        available_exceptions = [
                            exc for exc in st.session_state.selected_exceptions if exc in available_hardcoded]

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
                            df = df[df['Exception info'].isin(
                                selected_exceptions)]
                            st.info(
                                f"⚠️ Wyświetlane wiersze z Exception info: {', '.join(selected_exceptions)}")

                        else:
                            st.info("⚠️ Wyświetlane wszystkie wiersze")
                    else:
                        st.sidebar.warning(
                            "⚠️ Brak zahardkodowanych wartości w kolumnie Exception info")
                        st.sidebar.info(
                            f"💡 Dostępne wartości: {', '.join(df['Exception info'].dropna().unique()[:5])}...")
                else:
                    st.sidebar.warning(
                        "⚠️ Nie znaleziono kolumny 'Exception info'")
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
            total_exceptions = len(
                df[df['Exception info'].notna() & (df['Exception info'] != '')])

            col1, col2, col3 = st.columns([2, 2, 1])

            with col1:
                st.metric("Exception info (filtrowane)", total_exceptions)
                if len(exception_counts) > 0:
                    st.caption(
                        f"Top: {exception_counts.index[0]} ({exception_counts.iloc[0]})")

            with col2:
                # Statystyki City Name - liczenie unikalnych adresów z datą
                if 'City Name' in df.columns:
                    # Sprawdź czy wszystkie wymagane kolumny adresowe istnieją
                    address_columns = [
                        'Postal', 'City Name', 'Street Name', 'Street Num']
                    available_address_columns = [
                        col for col in address_columns if col in df.columns]

                    # Znajdź kolumnę z datą
                    date_column = None
                    for col in df.columns:
                        if col.upper() == 'DATA' or 'date' in col.lower():
                            date_column = col
                            break

                    # Minimum City Name + jedna inna kolumna adresowa
                    if len(available_address_columns) >= 2:
                        # Utwórz unikalne kombinacje adresów + data
                        if date_column and len(available_address_columns) == 4:
                            # Wszystkie kolumny adresowe + data dostępne
                            unique_columns = address_columns + \
                                [date_column]
                            unique_addresses = df[unique_columns].drop_duplicates(
                            )
                        elif date_column:
                            # Tylko dostępne kolumny + data
                            unique_columns = available_address_columns + \
                                [date_column]
                            unique_addresses = df[unique_columns].drop_duplicates(
                            )
                        elif len(available_address_columns) == 4:
                            # Wszystkie kolumny adresowe bez daty
                            unique_addresses = df[address_columns].drop_duplicates(
                            )
                        else:
                            # Tylko dostępne kolumny bez daty
                            unique_addresses = df[available_address_columns].drop_duplicates(
                            )

                        # Policz miasta w unikalnych adresach
                        city_counts = unique_addresses['City Name'].value_counts(
                        )
                        wroclaw_count = city_counts.get('WROCLAW', 0)
                        other_count = len(unique_addresses) - wroclaw_count

                        st.metric("WROCLAW (unikalne adresy)",
                                  wroclaw_count)
                        st.metric(
                            "Inne miasta (unikalne adresy)", other_count)
                        if date_column:
                            st.caption(
                                f"Łącznie unikalnych adresów z datą: {len(unique_addresses)}")
                        else:
                            st.caption(
                                f"Łącznie unikalnych adresów: {len(unique_addresses)}")
                    else:
                        # Fallback - liczenie bezpośrednio z City Name
                        city_counts = df['City Name'].value_counts()
                        wroclaw_count = city_counts.get('WROCLAW', 0)
                        other_count = len(df) - wroclaw_count

                        st.metric("WROCLAW", wroclaw_count)
                        st.metric("Wioski", other_count)
                        st.caption("⚠️ Brak pełnych danych adresowych")
                else:
                    st.info("Brak kolumny 'City Name'")

            with col3:
                st.empty()  # Pusty placeholder

            # Stwórz zakładki
            tab1, tab2, tab3 = st.tabs(
                ["📊 Dane", "🗺️ Mapa GPS", "🔍 Wyszukiwanie śladu"])

            with tab1:
                # Główna zawartość
                col1, col2 = st.columns([3, 1])

            with col1:
                if 'Driver ID:' in df.columns and selected_driver != 'Wszyscy':
                    st.header(f"📊 Driver ID: {selected_driver}")

                    # Podgląd danych
                    st.subheader("Podgląd danych")
                    st.dataframe(df.head(10), use_container_width=True)
                else:
                    st.header("📊 Podsumowanie dla wszystkich kierowców")

                    # Tabela podsumowująca dla wszystkich kierowców
                    if 'Driver ID:' in df.columns:
                        # Przygotuj dane do podsumowania
                        summary_data = []

                        for driver_id in df['Driver ID:'].dropna().unique():
                            driver_df = df[df['Driver ID:'] == driver_id]

                            # Liczba wyjątków
                            exception_count = len(driver_df[driver_df['Exception info'].notna() & (
                                driver_df['Exception info'] != '')])

                            # Statystyki miast
                            if 'City Name' in driver_df.columns:
                                # Sprawdź czy wszystkie wymagane kolumny adresowe istnieją
                                address_columns = [
                                    'Postal', 'City Name', 'Street Name', 'Street Num']
                                available_address_columns = [
                                    col for col in address_columns if col in driver_df.columns]

                                # Znajdź kolumnę z datą
                                date_column = None
                                for col in driver_df.columns:
                                    if col.upper() == 'DATA' or 'date' in col.lower():
                                        date_column = col
                                        break

                                # Minimum City Name + jedna inna kolumna adresowa
                                if len(available_address_columns) >= 2:
                                    # Utwórz unikalne kombinacje adresów + data
                                    if date_column and len(available_address_columns) == 4:
                                        # Wszystkie kolumny adresowe + data dostępne
                                        unique_columns = address_columns + \
                                            [date_column]
                                        unique_addresses = driver_df[unique_columns].drop_duplicates(
                                        )
                                    elif date_column:
                                        # Tylko dostępne kolumny + data
                                        unique_columns = available_address_columns + \
                                            [date_column]
                                        unique_addresses = driver_df[unique_columns].drop_duplicates(
                                        )
                                    elif len(available_address_columns) == 4:
                                        # Wszystkie kolumny adresowe bez daty
                                        unique_addresses = driver_df[address_columns].drop_duplicates(
                                        )
                                    else:
                                        # Tylko dostępne kolumny bez daty
                                        unique_addresses = driver_df[available_address_columns].drop_duplicates(
                                        )

                                    # Policz miasta w unikalnych adresach
                                    city_counts = unique_addresses['City Name'].value_counts(
                                    )
                                    wroclaw_count = city_counts.get(
                                        'WROCLAW', 0)
                                    other_count = len(
                                        unique_addresses) - wroclaw_count
                                else:
                                    # Fallback - liczenie bezpośrednio z City Name
                                    city_counts = driver_df['City Name'].value_counts(
                                    )
                                    wroclaw_count = city_counts.get(
                                        'WROCLAW', 0)
                                    other_count = len(
                                        driver_df) - wroclaw_count
                            else:
                                wroclaw_count = 0
                                other_count = 0

                            # Dodaj dane do podsumowania z skróconą nazwą Driver ID
                            short_driver_id = extract_driver_name(driver_id)
                            summary_data.append({
                                # Skrócona nazwa + oryginalna w nawiasach
                                'Driver ID': f"{short_driver_id} ({driver_id})",
                                'Exception Count': exception_count,
                                'WROCLAW': wroclaw_count,
                                'Wioski': other_count,
                                'Total Rows': len(driver_df)
                            })

                        # Utwórz DataFrame z podsumowaniem
                        summary_df = pd.DataFrame(summary_data)

                        # Sortuj według skróconych nazw Driver ID alfabetycznie
                        summary_df['Driver ID_short'] = summary_df['Driver ID'].apply(
                            lambda x: x.split(' (')[0] if ' (' in str(x) else str(x))
                        summary_df = summary_df.sort_values(
                            'Driver ID_short').drop('Driver ID_short', axis=1)

                        # Wyświetl tabelę podsumowującą
                        st.subheader("📋 Podsumowanie kierowców")
                        st.dataframe(summary_df, use_container_width=True)

                        # Dodaj przycisk eksportu tabeli podsumowującej
                        st.subheader("💾 Eksport podsumowania")
                        col_export1, col_export2 = st.columns(2)

                        with col_export1:
                            if st.button("📥 Pobierz podsumowanie (CSV)"):
                                csv_summary = summary_df.to_csv(index=False)
                                st.download_button(
                                    label="📥 Pobierz CSV",
                                    data=csv_summary,
                                    file_name=f"podsumowanie_kierowcow_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                    mime="text/csv"
                                )

                        with col_export2:
                            if st.button("📥 Pobierz podsumowanie (Excel)"):
                                output_summary = io.BytesIO()
                                with pd.ExcelWriter(output_summary, engine='openpyxl') as writer:
                                    summary_df.to_excel(
                                        writer, sheet_name='Podsumowanie', index=False)
                                output_summary.seek(0)

                                st.download_button(
                                    label="📥 Pobierz Excel",
                                    data=output_summary.getvalue(),
                                    file_name=f"podsumowanie_kierowcow_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                )

                        st.markdown("---")
                        st.subheader("📊 Szczegółowe dane")
                        st.dataframe(df.head(10), use_container_width=True)
                    else:
                        st.header("📊 Wszystkie dane")
                        st.dataframe(df.head(10), use_container_width=True)

            with col2:
                st.header("💾 Eksport")

                # Eksport danych - tylko gdy wybrano konkretnego kierowcę
                if 'Driver ID:' in df.columns and selected_driver != 'Wszyscy':
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
                else:
                    st.info(
                        "💡 Wybierz konkretnego kierowcę, aby eksportować szczegółowe dane")
                    st.info("📋 Użyj przycisków eksportu podsumowania poniżej")

                # Wyświetl dane w głównej kolumnie
                st.markdown("---")
                st.subheader("📋 Wszystkie dane")
                st.dataframe(df, use_container_width=True)

            with tab2:
                # Mapa GPS
                st.header("🗺️ Mapa GPS")

                # Sprawdź czy istnieją kolumny GPS
                if 'GPSX' in df.columns and 'GPSY' in df.columns:
                    # Sprawdź czy są dane GPS do wyświetlenia
                    gps_data = df[(df['GPSX'].notna()) & (df['GPSY'].notna()) &
                                  (df['GPSX'] != '') & (df['GPSY'] != '')]

                    if len(gps_data) > 0:
                        # Informacje o danych GPS
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric("Punkty GPS", len(gps_data))
                        with col2:
                            st.metric(
                                "Współrzędne X", f"{gps_data['GPSX'].min():.2f} - {gps_data['GPSX'].max():.2f}")
                        with col3:
                            st.metric(
                                "Współrzędne Y", f"{gps_data['GPSY'].min():.2f} - {gps_data['GPSY'].max():.2f}")

                        # Sprawdź format współrzędnych
                        sample_x = gps_data['GPSX'].iloc[0]
                        sample_y = gps_data['GPSY'].iloc[0]

                        if abs(sample_x) > 180 or abs(sample_y) > 90:
                            st.info(
                                f"🔍 Wykryto współrzędne UTM (X: {sample_x:.0f}, Y: {sample_y:.0f}) - konwertuję na współrzędne geograficzne")
                        else:
                            # Sprawdź kolejność współrzędnych
                            is_gpsx_lat = (sample_x >= 49 and sample_x <= 55)
                            is_gpsx_lon = (sample_x >= 14 and sample_x <= 24)

                            if is_gpsx_lat:
                                st.info(
                                    f"🔍 Wykryto współrzędne geograficzne - GPSX to szerokość ({sample_x:.6f}), GPSY to długość ({sample_y:.6f})")
                            elif is_gpsx_lon:
                                st.info(
                                    f"🔍 Wykryto współrzędne geograficzne - GPSX to długość ({sample_x:.6f}), GPSY to szerokość ({sample_y:.6f})")
                            else:
                                st.info(
                                    f"🔍 Wykryto współrzędne geograficzne (X: {sample_x:.6f}, Y: {sample_y:.6f}) - sprawdzam kolejność...")

                        # Legenda kolorów
                        st.markdown("**Legenda kolorów:**")
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.markdown("🔴 Czerwony - Inne")
                        with col2:
                            st.markdown("🟢 Zielony - DR RELEASED")
                        with col3:
                            st.markdown("🔵 Niebieski - COMM INS REL")
                        with col4:
                            st.markdown("🟠 Pomarańczowy - SIG OBTAINED")

                        # Inicjalizuj session state dla mapy GPS z unikalnym kluczem dla pliku
                        gps_map_key = f"gps_map_{file_key}"
                        gps_loaded_key = f"gps_loaded_{file_key}"

                        if gps_loaded_key not in st.session_state:
                            st.session_state[gps_loaded_key] = False
                        if gps_map_key not in st.session_state:
                            st.session_state[gps_map_key] = None

                        # Automatyczne ładowanie mapy GPS (jak w zakładce wyszukiwania śladu)
                        with st.spinner("🗺️ Ładowanie mapy GPS..."):
                            # Sprawdź czy mapa już została załadowana
                            if not st.session_state[gps_loaded_key] or st.session_state[gps_map_key] is None:
                                # Utwórz i zapisz mapę w session state
                                map_obj = create_gps_map(df)
                                if map_obj:
                                    st.session_state[gps_map_key] = map_obj
                                    st.session_state[gps_loaded_key] = True
                                else:
                                    st.warning(
                                        "⚠️ Nie udało się utworzyć mapy")
                                    st.session_state[gps_loaded_key] = False

                            # Wyświetl mapę jeśli została załadowana
                            if st.session_state[gps_loaded_key] and st.session_state[gps_map_key]:
                                st_folium(
                                    st.session_state[gps_map_key], width=700, height=500)
                            else:
                                st.warning(
                                    "⚠️ Nie udało się utworzyć mapy GPS")
                    else:
                        st.warning("⚠️ Brak danych GPS do wyświetlenia")
                else:
                    st.warning("⚠️ Brak kolumn GPSX i GPSY w danych")

            with tab3:
                # Wyszukiwanie śladu GPS
                st.header("🔍 Wyszukiwanie śladu GPS")

                if 'Numer' in df.columns and 'GPSX' in df.columns and 'GPSY' in df.columns:
                    # Pole do wklejenia numeru przesyłki
                    tracking_number = st.text_input(
                        "Wklej numer przesyłki:",
                        placeholder="Wprowadź numer przesyłki...",
                        help="Wklej numer przesyłki z kolumny 'Numer' aby znaleźć ślad GPS"
                    )

                    if tracking_number:
                        # Wyszukaj dane dla danego numeru przesyłki
                        tracking_data = df[df['Numer'].astype(str).str.contains(
                            str(tracking_number), case=False, na=False)]

                        if len(tracking_data) > 0:
                            st.success(
                                f"✅ Znaleziono {len(tracking_data)} rekordów dla numeru: {tracking_number}")

                            # Sprawdź czy są dane GPS
                            gps_tracking_data = tracking_data[(tracking_data['GPSX'].notna()) &
                                                              (tracking_data['GPSY'].notna()) &
                                                              (tracking_data['GPSX'] != '') &
                                                              (tracking_data['GPSY'] != '')]

                            if len(gps_tracking_data) > 0:
                                # Wyświetl informacje o śladzie
                                col1, col2 = st.columns(2)

                                with col1:
                                    st.subheader("📊 Informacje o śladzie")
                                    st.metric("Liczba punktów GPS",
                                              len(gps_tracking_data))

                                    # Wyświetl szczegóły pierwszego rekordu
                                    if len(gps_tracking_data) > 0:
                                        first_record = gps_tracking_data.iloc[0]
                                        st.write(
                                            f"**Driver ID:** {first_record.get('Driver ID:', 'Brak')}")
                                        st.write(
                                            f"**Data:** {first_record.get('DATA', 'Brak')}")
                                        st.write(
                                            f"**Miasto:** {first_record.get('City Name', 'Brak')}")
                                        st.write(
                                            f"**Exception info:** {first_record.get('Exception info', 'Brak')}")

                                        # Wyświetl informacje o współrzędnych
                                        st.write(
                                            f"**Współrzędne X:** {first_record.get('GPSX', 'Brak')}")
                                        st.write(
                                            f"**Współrzędne Y:** {first_record.get('GPSY', 'Brak')}")

                                        # Sprawdź format współrzędnych
                                        gps_x = first_record.get('GPSX', 0)
                                        gps_y = first_record.get('GPSY', 0)
                                        try:
                                            gps_x_num = float(gps_x)
                                            gps_y_num = float(gps_y)
                                            if abs(gps_x_num) > 180 or abs(gps_y_num) > 90:
                                                st.info(
                                                    "🔍 Format UTM - będzie konwertowane na współrzędne geograficzne")
                                            else:
                                                # Sprawdź kolejność współrzędnych
                                                is_gpsx_lat = (
                                                    gps_x_num >= 49 and gps_x_num <= 55)
                                                is_gpsx_lon = (
                                                    gps_x_num >= 14 and gps_x_num <= 24)

                                                if is_gpsx_lat:
                                                    st.info(
                                                        f"🔍 GPSX to szerokość ({gps_x_num:.6f}), GPSY to długość ({gps_y_num:.6f})")
                                                elif is_gpsx_lon:
                                                    st.info(
                                                        f"🔍 GPSX to długość ({gps_x_num:.6f}), GPSY to szerokość ({gps_y_num:.6f})")
                                                else:
                                                    st.info(
                                                        "🔍 Format geograficzny - sprawdzam kolejność...")
                                        except Exception:
                                            st.warning(
                                                "⚠️ Nie można określić formatu współrzędnych")

                                with col2:
                                    st.subheader("🗺️ Mapa śladu")
                                    # Utwórz mapę dla tego konkretnego śladu (automatycznie gdy zakładka jest aktywna)
                                    with st.spinner("🗺️ Ładowanie mapy śladu GPS..."):
                                        tracking_map = create_gps_map(
                                            gps_tracking_data)
                                        if tracking_map:
                                            st_folium(tracking_map,
                                                      width=500, height=400)
                                        else:
                                            st.warning(
                                                "⚠️ Nie udało się utworzyć mapy śladu")

                                # Wyświetl tabelę z danymi śladu
                                st.subheader("📋 Dane śladu")
                                st.dataframe(gps_tracking_data,
                                             use_container_width=True)

                                # Eksport śladu
                                st.subheader("💾 Eksport śladu")
                                col_export1, col_export2 = st.columns(2)

                                with col_export1:
                                    if st.button("📥 Pobierz ślad (CSV)"):
                                        csv_tracking = gps_tracking_data.to_csv(
                                            index=False)
                                        st.download_button(
                                            label="📥 Pobierz CSV",
                                            data=csv_tracking,
                                            file_name=f"slad_{tracking_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                                            mime="text/csv"
                                        )

                                with col_export2:
                                    if st.button("📥 Pobierz ślad (Excel)"):
                                        output_tracking = io.BytesIO()
                                        with pd.ExcelWriter(output_tracking, engine='openpyxl') as writer:
                                            gps_tracking_data.to_excel(
                                                writer, sheet_name='Slad', index=False)
                                        output_tracking.seek(0)

                                        st.download_button(
                                            label="📥 Pobierz Excel",
                                            data=output_tracking.getvalue(),
                                            file_name=f"slad_{tracking_number}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                        )
                            else:
                                st.warning(
                                    "⚠️ Brak danych GPS dla tego numeru przesyłki")
                                st.info("📋 Dostępne dane bez GPS:")
                                st.dataframe(
                                    tracking_data, use_container_width=True)
                        else:
                            st.error(
                                f"❌ Nie znaleziono żadnych rekordów dla numeru: {tracking_number}")

                            # Pokaż sugestie podobnych numerów
                            all_numbers = df['Numer'].dropna().astype(
                                str).unique()
                            similar_numbers = [num for num in all_numbers if str(
                                tracking_number).lower() in num.lower()]

                            if similar_numbers:
                                st.info("💡 Możliwe podobne numery:")
                                # Pokaż maksymalnie 5 sugestii
                                for num in similar_numbers[:5]:
                                    st.write(f"- {num}")
                else:
                    st.warning(
                        "⚠️ Brak wymaganych kolumn: 'Numer', 'GPSX' lub 'GPSY'")

else:
    # Instrukcje gdy nie ma pliku
    st.info("👆 Załaduj plik Excel, aby rozpocząć przetwarzanie danych.")

    st.markdown("""
    ## 🚀 Funkcje aplikacji:

    - **📁 Ładowanie plików Excel** - obsługa formatów .xlsx, .xls i .xlsb
    - **📅 Wybór dat** - kalendarz z opcjami: wszystkie daty, tylko soboty, niestandardowy wybór (zapamiętuje wybór)
    - **🚗 Wybór Driver ID** - filtrowanie danych według kierowcy z skróconymi nazwami (zapamiętuje wybór)
    - **⚠️ Exception info** - multiselect z zahardkodowanymi wartościami: DR RELEASED, COMM INS REL, SIG OBTAINED
    - **🗺️ Mapa GPS** - interaktywna mapa z punktami GPS (kolumny GPSX, GPSY) z kolorowym kodowaniem według Exception info
    - **🔍 Wyszukiwanie śladu** - wyszukiwanie pojedynczego śladu GPS po numerze przesyłki z osobnej mapą
    - **📊 Podgląd danych** - wyświetlanie pierwszych 10 wierszy
    - **💾 Eksport** - pobieranie danych w formacie CSV lub Excel

    ## 📝 Jak używać:
    1. Załaduj plik Excel używając przycisku w lewym panelu
    2. Wybierz opcję dat (wszystkie, tylko soboty, lub niestandardowy wybór) - wybór zostanie zapamiętany
    3. Wybierz Driver ID z listy rozwijanej - wybór zostanie zapamiętany
    4. Wybierz z zahardkodowanych wartości Exception info: DR RELEASED, COMM INS REL, SIG OBTAINED
    5. Przejrzyj dane w zakładce "Dane"
    6. Sprawdź mapę GPS w zakładce "Mapa GPS" (ładuje się tylko gdy zakładka jest aktywna)
    7. Wyszukaj konkretny ślad GPS w zakładce "Wyszukiwanie śladu" po numerze przesyłki
    8. Eksportuj wyniki w formacie CSV lub Excel

    ## ✨ Nowe funkcje:
    - **Skrócone nazwy Driver ID** - wyświetlanie tylko znaków 5-8 z nazwy dla lepszej czytelności
    - **Sortowanie** - Driver ID są posortowane numerycznie lub alfabetycznie
    - **Tabela podsumowująca** - pokazuje skróconą nazwę + oryginalną w nawiasach
    - **🗺️ Mapa GPS** - interaktywna mapa z punktami GPS z kolorowym kodowaniem według Exception info
    - **📊 Statystyki GPS** - wyświetlanie liczby punktów GPS i zakresu współrzędnych
    - **🔍 Wyszukiwanie śladu** - wyszukiwanie pojedynczego śladu GPS po numerze przesyłki z dedykowaną mapą
    - **📑 Zakładki** - podział na zakładki dla lepszej wydajności i organizacji
    """)

# Stopka
st.markdown("---")
st.markdown(
    "💡 **Wskazówka:** Aplikacja automatycznie cache'uje załadowane pliki dla lepszej wydajności.")
