from fuzzywuzzy import process
import subprocess
import json
import time
import pyautogui
import pyperclip
import json
import re


## Get highlight book title
def parse_clippings(file_path, remove_duplicates=False):
    """
    Parses the Kindle clippings from a specified file and optionally removes duplicates based on title and highlight text.

    Args:
        file_path (str): The path to the 'My Clippings.txt' file containing Kindle highlights.
        remove_duplicates (bool): If True, duplicate highlights based on title and text are removed. Defaults to False.


    Returns:
        dict: A dictionary where keys are book titles and values are lists of highlight details (location, timestamp, text).

    The function splits the content of the file by '==========', which is the delimiter used by Kindle
    to separate individual clippings. Each clipping is then parsed into its constituent parts: title,
    location, timestamp, and the highlight text itself. If 'remove_duplicates' is set to True, it ensures
    that only unique highlights (based on title and text) are included in the final output.
    """
    with open(file_path, "r", encoding="utf-8") as file:
        content = file.read()

    clippings = content.split("==========")
    parsed_clippings = {}
    seen_highlights = set()  # Set to track unique highlights if removal is enabled

    for clipping in clippings:
        lines = clipping.strip().split("\n")
        if len(lines) >= 4:
            book_title = lines[0].replace("\ufeff", "").strip()
            location = lines[1].split(" | ")[0].replace("- ", "").strip()
            timestamp = lines[1].split(" | ")[1].strip()
            highlight = "\n".join(lines[3:]).strip()

            # Define uniqueness based on title and highlight text
            identifier = (book_title, highlight)

            # Check for duplicates only if remove_duplicates is True
            if not remove_duplicates or identifier not in seen_highlights:
                if remove_duplicates:
                    seen_highlights.add(identifier)

                if book_title not in parsed_clippings:
                    parsed_clippings[book_title] = []

                parsed_clippings[book_title].append(
                    {
                        # "location": location,
                        # "timestamp": timestamp,
                        "highlight": highlight,
                    }
                )

    # Save to JSON file
    with open("parsed_highlights.json", "w", encoding="utf-8") as f:
        json.dump(parsed_clippings, f, indent=4, ensure_ascii=False)


def replace_special_characters(text, replacement_char="_"):
    """
    Replaces all non-alphanumeric characters (except spaces, dashes, and brackets) in the text with a specified replacement character.

    Args:
        text (str): The original string.
        replacement_char (str): The character to replace all non-alphanumeric characters (except spaces, dashes, and brackets) with.

    Returns:
        str: The modified string with special characters replaced, preserving spaces, dashes, and brackets.
    """
    # Replace any character that is not a letter, number, underscore, space, dash, or bracket with the specified replacement character
    return re.sub(r"[^\w\s\-\[\]\(\)]", replacement_char, text)


def read_calibre_device_metadata(path):
    """
    Parses a JSON file containing metadata from a Calibre-managed device.

    Args:
        path (str): The file path to the JSON metadata.

    Returns:
        dict: A dictionary mapping book titles to their respective Calibre application IDs.
    """
    try:
        with open(path, "r", encoding="utf-8") as file:
            calibre_metadata = json.load(
                file
            )  # This loads the JSON array into a Python list
            calibre_books_parsed = {}
            for calibre_item in calibre_metadata:
                book_title = (
                    replace_special_characters(
                        calibre_item["title"], replacement_char="_"
                    )
                    + f' ({calibre_item["authors"][0]})'
                )
                book_id = calibre_item["application_id"]
                calibre_books_parsed[book_title] = book_id
        return calibre_books_parsed
    except json.JSONDecodeError as e:
        print("Error decoding JSON:", e)
    except IOError as e:
        print("Error reading file:", e)
    except Exception as e:
        print("An unknown error occurred:", e)
    return None


def list_all_books_and_save():
    """
    Retrieves all books from the Calibre library using calibredb.exe, including their IDs, titles, authors, and paths,
    and saves this data to 'calibre_books.json' in the root directory.

    Returns:
        bool: True if the file was successfully written, False otherwise.

    This function calls the calibredb CLI with flags to format the output as JSON for machine readability and specifies
    the fields to include ID, title, author names, and file paths. It writes the output to a JSON file.
    """
    try:
        # Using subprocess to call calibredb.exe with the necessary arguments
        result = subprocess.run(
            [
                "calibredb.exe",
                "list",
                "--for-machine",
                "--fields",
                "id,title,authors,formats",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        # Parsing the output as JSON
        books = json.loads(result.stdout)

        # Writing the books data to a JSON file
        with open("calibre_books.json", "w", encoding="utf-8") as f:
            json.dump(books, f, indent=4, ensure_ascii=False)

        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to execute calibredb: {e}")
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON data: {e}")
    except IOError as e:
        print(f"Failed to write to file: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    return False


def find_best_match_book_id_and_save(
    highlights_path, calibre_books_path, calibre_metadata
):
    """
    Matches book titles from parsed highlights to book IDs in Calibre books data, using fuzzy matching,
    and saves a detailed mapping including titles, paths, and highlights to 'device_to_calibre_mapping.json'.

    Args:
        highlights_path (str): Path to the JSON file containing parsed highlights.
        calibre_books_path (str): Path to the JSON file containing books data from Calibre.
        calibre_metadata (dict): Metadata mapping book titles to Calibre IDs.

    Returns:
        None: Saves the mapping results to 'device_to_calibre_mapping.json' without returning any value.
    """

    # Load highlights data
    with open(highlights_path, "r", encoding="utf-8") as file:
        highlights_data = json.load(file)

    # # Load Calibre books data
    with open(calibre_books_path, "r", encoding="utf-8") as file:
        calibre_books = json.load(file)

    # Map titles from Calibre books to their IDs and paths
    title_to_details = {
        book["id"]: {"title": book["title"], "path": book["formats"]}
        for book in calibre_books
    }

    # Prepare to map highlights to Calibre book details
    matches = []

    # Loop through each title in the highlights data
    for highlight_title, highlights in highlights_data.items():
        best_match = process.extractOne(
            highlight_title, calibre_metadata.keys(), score_cutoff=80
        )
        if best_match:
            # Retrieve matching book details from Calibre
            book_id = calibre_metadata[best_match[0]]
            if book_id:
                match_info = {
                    "device_title": highlight_title,
                    "calibre_title": best_match[0],
                    "mapped_title": title_to_details[book_id]["title"],
                    "book_id": book_id,
                    "matched_score": best_match[1],
                    "book_path": title_to_details[book_id]["path"],
                    "highlights": highlights,
                }
                matches.append(match_info)

    # Save the matched data to a JSON file
    with open("device_to_calibre_mapping.json", "w", encoding="utf-8") as file:
        json.dump(matches, file, indent=4, ensure_ascii=False)
    return matches


def open_book_in_calibre_viewer(book_path):
    """
    Opens a book in Calibre's eBook viewer using the specified path.

    Args:
        book_path (str): The path to the book file.
    """
    try:
        # Start Calibre Viewer with the specified book
        subprocess.Popen(["ebook-viewer", book_path])
        time.sleep(15)
    except subprocess.CalledProcessError as e:
        print(f"Failed to open book: {e}")
    except Exception as e:
        print(f"An error occurred: {e}")


def perform_text_operations(highlight_texts):
    """
    Interacts with the user to verify if highlights were found correctly and handles user responses.

    Args:
        highlight_texts (list): A list of text strings to be verified.

    Returns:
        list: A list of highlights that were not found according to user input.
    """
    highlights_not_found = []  # List to store highlights not confirmed by the user

    for idx, text in enumerate(highlight_texts):
        pyautogui.hotkey("ctrl", "f")  # Open search window
        pyperclip.copy(text)  # Copy text to clipboard
        pyautogui.hotkey("ctrl", "v")  # Paste the text

        pyautogui.hotkey("enter")  # Paste the text
        pyautogui.hotkey("enter")  # Paste the text

        user_confirmation = pyautogui.confirm(
            f"Confirm if the highlight was found correctly.\n Highlight {idx+1} of {len(highlight_texts)}",
            buttons=["Yes", "No"],
        )

        if user_confirmation == "Yes":
            pyautogui.keyDown("shiftleft")
            pyautogui.keyDown("shiftright")
            pyautogui.hotkey("right", "left")
            pyautogui.keyUp("shiftleft")
            pyautogui.keyUp("shiftright")
            pyautogui.press("q")  # Press 'Q'
        elif user_confirmation == "No":
            highlights_not_found.append(text)
    if highlights_not_found:
        pyautogui.alert(
            f"Some highlights were not found: {len(highlights_not_found)} skipped."
        )
    else:
        pyautogui.alert(f"All highlights applied successfully")
    return highlights_not_found


def main():
    print(
        """
        This program automates the process of highlighting books in the Calibre library by managing highlights in JSON format.
        If your source of highlights is from Kindle, this program can parse 'My Clippings.txt' into JSON format.
        
        The expected JSON format for highlights is:
        {
            "Book Name": [
                {"highlight": "Highlight 1"},
                {"highlight": "Highlight 2"},
                {"highlight": "Highlight 3"},
                {"highlight": "Highlight 4"},
            ],
        }
        """
    )

    # Prompt user for the path to 'My Clippings.txt'
    clippings_path = (
        input(
            'Enter "My Clippings.txt" path or press Enter if it is located in root: '
        ).strip()
        or "My Clippings.txt"
    )

    # Whether to remove duplicated highlights
    is_remove_duplicates = input(
        'Enter "Y" or "y" to remove duplicated highlights: '
    ).strip()

    is_remove_duplicates = bool(is_remove_duplicates in ("Y", "y"))

    # Parse Kindle clippings
    parse_clippings(clippings_path, is_remove_duplicates)
    print(
        f"Highlights from '{clippings_path}' have been parsed and saved to 'parsed_highlights.json'.\n"
    )

    # Prompt user for the path to 'metadata.calibre'
    calibre_metadata_path = (
        input(
            'Enter "metadata.calibre" path or press Enter if it is located in root.\n(This file is usually located in your Kindle device root folder): '
        ).strip()
        or "metadata.calibre"
    )

    # Read and process Calibre device metadata
    calibre_metadata = read_calibre_device_metadata(calibre_metadata_path)
    if not calibre_metadata:
        print("Failed to read or process the Calibre metadata.")
        return

    # Retrieve and save all books from the Calibre library
    if list_all_books_and_save():
        print("Calibre library books have been saved to 'calibre_books.json'.")
    else:
        print(
            "Failed to retrieve or save Calibre library books. Make sure there is no other calibre program such as calibre-server.exe or the main calibre program is running."
        )

    # Match highlights to books and save the mapping
    matches = find_best_match_book_id_and_save(
        "parsed_highlights.json", "calibre_books.json", calibre_metadata
    )

    print(
        "Books in Calibre Library has been matched to the Books in 'My Clippings.Text'. Here below the summary of the findings"
    )
    # Display the mapping summary
    print(
        "{:<8} {:<14} {:<16} {:<100}".format(
            "Book ID", "Matching Score", "Total Highlights", "Title"
        )
    )
    for book in matches:
        print(
            "{:<8} {:<14} {:<16} {:<100}".format(
                book["book_id"],
                book["matched_score"],
                len(book["highlights"]),
                book["device_title"],
            )
        )

    # Allow the user to select a book to open
    book_id = int(
        input(
            "From the above list, enter a {Book ID} to open the book in Calibre ebook Viewer and start highlighting process: "
        ).strip()
    )
    book_path = None

    for book in matches:
        if book["book_id"] == book_id:
            book_highlights = [
                highlight["highlight"] for highlight in book["highlights"]
            ]
            book_path = book["book_path"][0]
            break

    if not book_path:
        print("Book path not found. Please check the Book ID and try again.")
        return

    # Open the book in Calibre Book Viewer
    print("Opening book in Calibre Book Viewer ...")
    open_book_in_calibre_viewer(book_path)
    print("Book is open.")
    print("Highlighting is in progress....")

    # Perform text operations
    highlights_not_found = perform_text_operations(book_highlights)
    print("Highlighting complete.")
    if highlights_not_found:
        print("Some highlights were not found:")
        print(highlights_not_found)
    else:
        print("All highlights were successfully found and marked.")

if __name__ == "__main__":
    main()