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
                        exc for exc in hardcoded_exceptions if exc in df['Exception info'].values]

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

            # Wyświetl dane
            st.markdown("---")
            st.subheader("📋 Dane")
            st.dataframe(df, use_container_width=True)

else:
    # Instrukcje gdy nie ma pliku
    st.info("👆 Załaduj plik Excel, aby rozpocząć przetwarzanie danych.")

    st.markdown("""
    ## 🚀 Funkcje aplikacji:
    
    - **📁 Ładowanie plików Excel** - obsługa formatów .xlsx, .xls i .xlsb
    - **📅 Wybór dat** - kalendarz z opcjami: wszystkie daty, tylko soboty, niestandardowy wybór (zapamiętuje wybór)
    - **🚗 Wybór Driver ID** - filtrowanie danych według kierowcy z skróconymi nazwami (zapamiętuje wybór)
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
    
    ## ✨ Nowe funkcje:
    - **Skrócone nazwy Driver ID** - wyświetlanie tylko znaków 5-8 z nazwy dla lepszej czytelności
    - **Sortowanie** - Driver ID są posortowane numerycznie lub alfabetycznie
    - **Tabela podsumowująca** - pokazuje skróconą nazwę + oryginalną w nawiasach
    """)

# Stopka
st.markdown("---")
st.markdown(
    "💡 **Wskazówka:** Aplikacja automatycznie cache'uje załadowane pliki dla lepszej wydajności.")
