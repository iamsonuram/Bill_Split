# Bill Splitter App

## Overview

The **Bill Splitter App** is a Streamlit-based web application designed to simplify splitting bills among groups of friends or colleagues. It allows users to upload a bill image, extract items and taxes using OCR, select items they consumed, and calculate individual shares. The app supports UPI payments by generating payment links for easy settlement. Key features include user registration, group management, bill processing, and fair cost distribution.

This project uses SQLite for data storage (with plans to support persistent storage on deployment) and integrates with the Mistral API for OCR and bill item extraction.

## Features

- **User Authentication**: Register and sign in using a phone number and password.
- **Group Management**: Create groups, add members, and manage group activities.
- **Bill Upload and OCR**: Upload bill images (JPG) and extract items and taxes using Mistral's OCR and agent API.
- **Item Selection**: Select items you consumed with quantity adjustments and see real-time updates.
- **Fair Splitting**: Automatically calculates each member's share based on selected items and taxes.
- **UPI Payment Links**: Generates clickable UPI links for easy payment to the bill uploader.
- **Persistent Storage**: Supports SQLite with persistent storage on Streamlit Community Cloud using the `/data` directory.

## Prerequisites

- Python 3.8 or higher
- A GitHub account (for deployment)
- A Mistral API key for OCR and bill processing (sign up at [Mistral AI](https://mistral.ai/))
- A UPI app on your phone (e.g., Google Pay, PhonePe) to test payment links

## Setup Instructions

### 1. Clone the Repository
Clone this repository to your local machine:

```bash
git clone https://github.com/your-username/bill-splitter-app.git
cd bill-splitter-app
```

Replace `your-username` with your GitHub username.

### 2. Install Dependencies
Create a virtual environment and install the required packages:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

The `requirements.txt` file includes:

```
streamlit
mistralai
pillow
bcrypt
```

### 3. Run the App Locally
Start the Streamlit app:

```bash
streamlit run app.py
```

- The app will open in your default browser at `http://localhost:8501`.
- A local SQLite database (`bill_splitter.db`) will be created in the `/data` directory if it doesn't exist.

## Usage

1. **Register or Sign In**:
   - Use the "Register" tab to create a new account with your name, phone number (10 digits, Indian standards), and password.
   - Use the "Sign In" tab to log in with your phone number and password.

2. **Set Up Your UPI ID**:
   - After signing in, you'll be prompted to enter your UPI ID (e.g., `yourname@upi`).
   - This is required for generating payment links.

3. **Create or Join a Group**:
   - In the sidebar, create a new group by entering a group name and clicking "Create Group".
   - If you're the group owner, add members by providing their name and phone number (they must be registered users).

4. **Upload a Bill**:
   - Select a group from the dropdown.
   - Upload a bill image (JPG format). The app will process the image using OCR to extract items and taxes.

5. **Select Items**:
   - Tick the items you consumed and adjust quantities using the "Increase" and "Decrease" buttons.
   - The app updates selections in real-time and shows what each member has selected.

6. **Finalize and Pay**:
   - Click "Next" to calculate your share of the bill.
   - A summary will show your total, including items and taxes.
   - If you're not the bill uploader, a UPI payment link will be generated to pay the uploader.


## Database Management

- **Local Database**: When running locally, the SQLite database is stored as `bill_splitter.db` in the `/data` directory.
- **Deployed Database**: On Streamlit Community Cloud, the database is stored in `/data/bill_splitter.db` to ensure persistence across app restarts.
- **Migration**: To migrate an existing database, use the upload method described in the deployment section.
- **Future Improvement**: Consider switching to a cloud database like PostgreSQL (e.g., on Supabase) for better scalability and concurrent access.


## Future Improvements

- **Cloud Database**: Migrate to PostgreSQL or another cloud database for better scalability.
- **QR Code for UPI**: Add a QR code option for UPI payments as a fallback for devices where links aren’t clickable.
- **Mobile Responsiveness**: Enhance CSS for better mobile layout.
- **Email Notifications**: Send payment reminders via email.
- **Multi-Currency Support**: Allow splitting bills in different currencies.

## Contributing

Contributions are welcome! Please fork the repository, make your changes, and submit a pull request.

1. Fork the repository.
2. Create a new branch (`git checkout -b feature/your-feature`).
3. Commit your changes (`git commit -m "Add your feature"`).
4. Push to the branch (`git push origin feature/your-feature`).
5. Open a pull request.

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE.txt) file for details.

## Contact

For questions or feedback, please open an issue on GitHub or contact the maintainer at [sonupranu04@gmail.com](mailto:sonupranu04@gmail.com).
