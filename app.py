import streamlit as st
import base64
import json
import sqlite3
import bcrypt
import re
from mistralai import Mistral
from PIL import Image
import io

# === CONFIGURATION ===
api_key = 'h4ZAJ1nXeDBwDOfbo6bGuGA2lLN9OLgU'
agent_id = "ag:79ec7e4f:20250307:ocr:975dc3a6"  # Replace with your actual Agent ID
DB_FILE = "bill_splitter.db"

# === DATABASE SETUP ===
def init_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()
    # Create users table if it doesn't exist
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        phone TEXT PRIMARY KEY,
        password TEXT NOT NULL,
        upi_id TEXT
    )''')
    # Check if the 'name' column exists in the users table
    c.execute("PRAGMA table_info(users)")
    columns = [col[1] for col in c.fetchall()]
    if 'name' not in columns:
        # Add the 'name' column with a default value
        c.execute("ALTER TABLE users ADD COLUMN name TEXT NOT NULL DEFAULT ''")
        # Update existing users to set name as phone number
        c.execute("UPDATE users SET name = phone WHERE name = ''")
    # Create other tables
    c.execute('''CREATE TABLE IF NOT EXISTS groups (
        group_name TEXT PRIMARY KEY,
        owner_phone TEXT NOT NULL,
        FOREIGN KEY (owner_phone) REFERENCES users(phone)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS group_members (
        group_name TEXT,
        member_phone TEXT,
        PRIMARY KEY (group_name, member_phone),
        FOREIGN KEY (group_name) REFERENCES groups(group_name),
        FOREIGN KEY (member_phone) REFERENCES users(phone)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS bills (
        group_name TEXT,
        uploader_phone TEXT,
        items TEXT,  -- JSON string of items
        taxes TEXT,  -- JSON string of taxes
        selections TEXT,  -- JSON string of selections
        PRIMARY KEY (group_name),
        FOREIGN KEY (group_name) REFERENCES groups(group_name),
        FOREIGN KEY (uploader_phone) REFERENCES users(phone)
    )''')
    conn.commit()
    return conn

# === DATABASE FUNCTIONS ===
def get_db_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)

def add_user(phone, name, password):
    hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (phone, name, password, upi_id) VALUES (?, ?, ?, ?)", (phone, name, hashed, ""))
        conn.commit()
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()
    return True

def verify_user(phone, password):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT password FROM users WHERE phone = ?", (phone,))
    result = c.fetchone()
    conn.close()
    if result and bcrypt.checkpw(password.encode('utf-8'), result[0]):
        return True
    return False

def update_upi_id(phone, upi_id):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("UPDATE users SET upi_id = ? WHERE phone = ?", (upi_id, phone))
    conn.commit()
    conn.close()

def get_user(phone):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT phone, name, upi_id FROM users WHERE phone = ?", (phone,))
    result = c.fetchone()
    conn.close()
    if result:
        return {"phone": result[0], "name": result[1], "upi_id": result[2]}
    return None

def create_group(group_name, owner_phone):
    conn = get_db_connection()
    c = conn.cursor()
    try:
        c.execute("INSERT INTO groups (group_name, owner_phone) VALUES (?, ?)", (group_name, owner_phone))
        c.execute("INSERT INTO group_members (group_name, member_phone) VALUES (?, ?)", (group_name, owner_phone))
        conn.commit()
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()
    return True

def add_member_to_group(group_name, member_name, member_phone):
    conn = get_db_connection()
    c = conn.cursor()
    # Check if member exists in users
    c.execute("SELECT phone FROM users WHERE phone = ?", (member_phone,))
    if not c.fetchone():
        conn.close()
        return False, "User not registered."
    try:
        c.execute("INSERT INTO group_members (group_name, member_phone) VALUES (?, ?)", (group_name, member_phone))
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return False, "Member already in group."
    conn.close()
    return True, None

def get_user_groups(phone):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT group_name FROM group_members WHERE member_phone = ?", (phone,))
    groups = [row[0] for row in c.fetchall()]
    conn.close()
    return groups

def get_group(group_name):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT owner_phone FROM groups WHERE group_name = ?", (group_name,))
    owner = c.fetchone()
    if not owner:
        conn.close()
        return None
    c.execute("SELECT member_phone FROM group_members WHERE group_name = ?", (group_name,))
    members = [row[0] for row in c.fetchall()]
    group = {
        "group_name": group_name,
        "owner": owner[0],
        "members": []
    }
    for member_phone in members:
        user = get_user(member_phone)
        if user:
            group["members"].append({
                "name": user["name"],
                "phone": user["phone"],
                "upi_id": user["upi_id"]
            })
    conn.close()
    return group

def save_bill_data(group_name, uploader_phone, items, taxes):
    conn = get_db_connection()
    c = conn.cursor()
    items_json = json.dumps(items)
    taxes_json = json.dumps(taxes)
    selections_json = json.dumps({})
    try:
        c.execute("INSERT OR REPLACE INTO bills (group_name, uploader_phone, items, taxes, selections) VALUES (?, ?, ?, ?, ?)",
                  (group_name, uploader_phone, items_json, taxes_json, selections_json))
        conn.commit()
    finally:
        conn.close()

def load_bill_data(group_name):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT uploader_phone, items, taxes, selections FROM bills WHERE group_name = ?", (group_name,))
    result = c.fetchone()
    conn.close()
    if result:
        return {
            "uploader": result[0],
            "items": json.loads(result[1]),
            "taxes": json.loads(result[2]),
            "selections": json.loads(result[3])
        }
    return None

def update_bill_selections(group_name, selections):
    conn = get_db_connection()
    c = conn.cursor()
    selections_json = json.dumps(selections)
    c.execute("UPDATE bills SET selections = ? WHERE group_name = ?", (selections_json, group_name))
    conn.commit()
    conn.close()

# === OCR AND BILL EXTRACTION FUNCTIONS ===
def encode_image(image_file):
    try:
        return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        st.error(f"Error encoding image: {e}")
        return None

def get_ocr_markdown(client, base64_image):
    try:
        ocr_response = client.ocr.process(
            model="mistral-ocr-latest",
            document={
                "type": "image_url",
                "image_url": f"data:image/jpeg;base64,{base64_image}"
            }
        )
        return ocr_response.pages[0].markdown
    except Exception as e:
        st.error(f"OCR failed: {e}")
        return None

def extract_structured_info_from_markdown(client, markdown_text, agent_id):
    try:
        response = client.agents.complete(
            agent_id=agent_id,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "This is a scanned bill in markdown format. "
                        "Extract all items with fields: Item Name, Quantity, Price (price per unit), and Total (if available). "
                        "Price (price per unit) must always be a number (not null). If Price (price per unit) is not directly available, "
                        "calculate it as Total divided by Quantity if both are present. If Price cannot be determined, exclude the item from the output. "
                        "Also include the overall total and any taxes (e.g., GST, service tax, or other charges) with their names and amounts. "
                        "Format the output as valid JSON. Ensure taxes are listed as an array of objects with 'name' and 'amount' fields. "
                        "Do not include any extra text, comments, explanations, or markdown formatting (such as ```json or ```) outside the JSON structure.\n\n"
                        f"{markdown_text}"
                    )
                }
            ]
        )
        raw_output = response.choices[0].message.content.strip()
        cleaned_output = re.sub(r'^```json\s*\n|```$', '', raw_output, flags=re.MULTILINE)
        return cleaned_output
    except Exception as e:
        st.error(f"Agent processing failed: {e}")
        return None

# === UPI PAYMENT LINK ===
def generate_upi_link(upi_id, name, amount):
    return f"upi://pay?pa={upi_id}&pn={name}&am={amount}&cu=INR"

# === PHONE NUMBER VALIDATION ===
def is_valid_indian_phone(phone):
    pattern = r'^\d{10}$'
    return bool(re.match(pattern, phone))

# === STREAMLIT UI ===
st.title("💸 Bill Splitter App with Groups")

# Initialize database
init_db()

# === PERSIST USER LOGIN ===
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_phone = None
    st.session_state.user_name = None

if st.session_state.user_phone:
    user_data = get_user(st.session_state.user_phone)
    if user_data:
        st.session_state.logged_in = True
        st.session_state.user_name = user_data["name"]
    else:
        st.session_state.logged_in = False
        st.session_state.user_phone = None
        st.session_state.user_name = None

if not st.session_state.logged_in:
    tab1, tab2 = st.tabs(["Register", "Sign In"])
    
    # Registration
    with tab1:
        st.header("Register")
        with st.form("register_form"):
            name = st.text_input("Your Name")
            phone = st.text_input("Phone Number (10 digits)")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Register"):
                if not name:
                    st.error("Name is required!")
                elif not is_valid_indian_phone(phone):
                    st.error("Phone number must be exactly 10 digits!")
                elif add_user(phone, name, password):
                    st.success("Registered successfully! Please sign in.")
                else:
                    st.error("Phone number already registered!")
    
    # Sign In
    with tab2:
        st.header("Sign In")
        with st.form("signin_form"):
            phone = st.text_input("Phone Number")
            password = st.text_input("Password", type="password")
            if st.form_submit_button("Sign In"):
                if verify_user(phone, password):
                    user_data = get_user(phone)
                    st.session_state.logged_in = True
                    st.session_state.user_phone = phone
                    st.session_state.user_name = user_data["name"]
                    st.rerun()
                else:
                    st.error("Invalid phone number or password.")
else:
    user_phone = st.session_state.user_phone
    user_name = st.session_state.user_name
    user_data = get_user(user_phone)
    
    # Check for UPI ID
    if not user_data["upi_id"]:
        st.header("Update Your UPI ID")
        with st.form("upi_form"):
            upi_id = st.text_input("Enter your UPI ID (e.g., yourname@upi)")
            if st.form_submit_button("Update UPI ID"):
                update_upi_id(user_phone, upi_id)
                st.success("UPI ID updated successfully!")
                st.rerun()
    else:
        # Main App
        st.sidebar.header(f"Welcome, {user_name}")
        if st.sidebar.button("Sign Out"):
            st.session_state.logged_in = False
            st.session_state.user_phone = None
            st.session_state.user_name = None
            st.rerun()
        
        # Group Creation and Management
        st.sidebar.header("Create or Join a Group")
        group_name = st.sidebar.text_input("Enter a group name")
        
        if st.sidebar.button("Create Group"):
            if create_group(group_name, user_phone):
                st.sidebar.success(f"Group '{group_name}' created!")
            else:
                st.sidebar.warning("Group name already exists!")
        
        # Show Groups
        st.header("Your Groups")
        user_groups = get_user_groups(user_phone)
        if not user_groups:
            st.write("You are not part of any groups yet.")
        else:
            selected_group = st.selectbox("Select a group", user_groups)
            if selected_group:
                group = get_group(selected_group)
                if not group:
                    st.error("Group not found.")
                    st.stop()
                
                # Add Members to Group (Only for Owner)
                if user_phone == group["owner"]:
                    with st.form("add_member"):
                        member_name = st.text_input("Member Name")
                        member_phone = st.text_input("Member Phone Number")
                        submitted = st.form_submit_button("Add Member")
                        if submitted and member_name and member_phone:
                            success, message = add_member_to_group(selected_group, member_name, member_phone)
                            if success:
                                st.success(f"Added {member_name} to the group!")
                                st.rerun()
                            else:
                                st.warning(message)
                
                # Display Group Members
                st.subheader(f"Group: {selected_group}")
                st.write("### Members")
                all_members = [{"name": get_user(group["owner"])["name"], "phone": group["owner"], "upi_id": get_user(group["owner"])["upi_id"]}] + group["members"]
                for member in all_members:
                    st.write(f"- {member['name']} (Phone: {member['phone']}, UPI: {member['upi_id'] or 'Not set'})")
                
                # Bill Upload and Splitting
                st.markdown("---")
                st.subheader("Upload and Split Bill")
                
                # Load bill data for this group
                group_bill_data = load_bill_data(selected_group)
                if not group_bill_data:
                    group_bill_data = {
                        "uploader": "",
                        "items": [],
                        "taxes": [],
                        "selections": {}
                    }
                
                # Bill Upload (Only for Owner or Members)
                if not group_bill_data["items"]:
                    uploaded_file = st.file_uploader("Upload Bill Image (JPG)", type=["jpg", "jpeg"])
                    if uploaded_file:
                        client = Mistral(api_key=api_key)
                        uploaded_file.seek(0)
                        base64_img = encode_image(uploaded_file)
                        if base64_img:
                            with st.spinner("Processing your image..."):
                                markdown_text = get_ocr_markdown(client, base64_img)
                            if markdown_text:
                                with st.spinner("Processing your image..."):
                                    structured_output = extract_structured_info_from_markdown(client, markdown_text, agent_id)
                                if structured_output:
                                    try:
                                        parsed_data = json.loads(structured_output)
                                        items = [
                                            {**item, "index": idx} for idx, item in enumerate(parsed_data.get("items", []))
                                        ]
                                        taxes = parsed_data.get("taxes", [])
                                        save_bill_data(selected_group, user_phone, items, taxes)
                                        st.success("Bill processed successfully!")
                                        st.rerun()
                                    except json.JSONDecodeError as e:
                                        st.error(f"Error parsing bill data: {e}")
                                        st.error(f"Raw output: {structured_output}")
                
                # Item Selection with Quantity
                if group_bill_data["items"]:
                    st.subheader("Select Items You Consumed")
                    if user_phone not in group_bill_data["selections"]:
                        group_bill_data["selections"][user_phone] = {}
                    
                    if 'error_message' not in st.session_state:
                        st.session_state.error_message = ""
                    
                    for item in group_bill_data["items"]:
                        item_key = f"{item['item_name']}_{item['index']}"
                        if item_key not in group_bill_data["selections"][user_phone]:
                            group_bill_data["selections"][user_phone][item_key] = {
                                "selected": False,
                                "quantity": 0
                            }
                        
                        col1, col2, col3, col4 = st.columns([3, 1, 1, 2])
                        
                        # Checkbox for item selection
                        with col1:
                            current_selection = group_bill_data["selections"][user_phone][item_key]
                            is_selected = st.checkbox(
                                f"{item['item_name']}",
                                key=f"cb_{item['item_name']}_{item['index']}_{user_phone}",
                                value=current_selection["selected"]
                            )
                            # Update selection and quantity based on checkbox
                            if is_selected and not current_selection["selected"]:
                                group_bill_data["selections"][user_phone][item_key]["selected"] = True
                                if current_selection["quantity"] == 0:
                                    group_bill_data["selections"][user_phone][item_key]["quantity"] = 1
                            elif not is_selected and current_selection["selected"]:
                                group_bill_data["selections"][user_phone][item_key]["selected"] = False
                                group_bill_data["selections"][user_phone][item_key]["quantity"] = 0
                            update_bill_selections(selected_group, group_bill_data["selections"])
                        
                        # Quantity controls
                        max_qty = item['quantity']
                        current_qty = group_bill_data["selections"][user_phone][item_key]["quantity"]
                        
                        with col2:
                            if st.button("Increase", key=f"inc_{item['item_name']}_{item['index']}_{user_phone}"):
                                if current_qty < max_qty:
                                    group_bill_data["selections"][user_phone][item_key]["quantity"] += 1
                                    group_bill_data["selections"][user_phone][item_key]["selected"] = True
                                    st.session_state.error_message = ""
                                    update_bill_selections(selected_group, group_bill_data["selections"])
                                    st.rerun()
                                else:
                                    st.session_state.error_message = f"Cannot exceed original quantity ({max_qty}) for {item['item_name']}!"
                        
                        with col3:
                            if st.button("Decrease", key=f"dec_{item['item_name']}_{item['index']}_{user_phone}"):
                                if current_qty > 1:
                                    group_bill_data["selections"][user_phone][item_key]["quantity"] -= 1
                                    group_bill_data["selections"][user_phone][item_key]["selected"] = True
                                    st.session_state.error_message = ""
                                    update_bill_selections(selected_group, group_bill_data["selections"])
                                    st.rerun()
                                elif current_qty == 1:
                                    st.session_state.error_message = f"Minimum quantity is 1 for {item['item_name']} - remove tick if you have not ordered it!"
                                else:
                                    st.session_state.error_message = f"Quantity is already 0 for {item['item_name']}!"
                        
                        # Display quantity and price
                        with col4:
                            st.write(f"Qty: {current_qty}/{max_qty} | Price per unit: ₹{item['price_per_unit']:.2f}")
                    
                    # Display error message if any
                    if st.session_state.error_message:
                        st.error(st.session_state.error_message)
                    
                    # Display Selections by All Members
                    st.markdown("---")
                    st.subheader("Selections by All Members")
                    for member_phone, selections in group_bill_data["selections"].items():
                        member_name = next((m["name"] for m in all_members if m["phone"] == member_phone), member_phone)
                        selected_items = []
                        for item_key, data in selections.items():
                            if data["selected"]:
                                item_name = item_key.split("_")[0]
                                qty = data["quantity"]
                                selected_items.append(f"{item_name} (Qty: {qty})")
                        st.write(f"{member_name}: {', '.join(selected_items) if selected_items else 'None'}")
                    
                    # Finalize and Calculate
                    if st.button("Next"):
                        # Calculate per-user totals
                        total_tax = sum(tax["amount"] for tax in group_bill_data["taxes"])
                        num_members = len(all_members)
                        tax_per_person = total_tax / num_members if num_members > 0 else 0
                        
                        user_totals = {}
                        for member in all_members:
                            member_phone = member["phone"]
                            user_totals[member_phone] = {"amount": tax_per_person, "items": []}
                        
                        # Calculate shared item costs
                        for item in group_bill_data["items"]:
                            item_key = f"{item['item_name']}_{item['index']}"
                            selectors = []
                            total_selected_qty = 0
                            for member_phone, selections in group_bill_data["selections"].items():
                                if item_key in selections and selections[item_key]["selected"]:
                                    qty = selections[item_key]["quantity"]
                                    if qty > 0:
                                        selectors.append((member_phone, qty))
                                        total_selected_qty += qty
                            
                            if total_selected_qty > 0:
                                # Total cost of the item
                                item_total_cost = item["price_per_unit"] * item["quantity"]
                                for selector_phone, qty in selectors:
                                    user_share = (qty / total_selected_qty) * item_total_cost
                                    user_totals[selector_phone]["amount"] += user_share
                                    user_totals[selector_phone]["items"].append({
                                        "name": item["item_name"],
                                        "cost": user_share,
                                        "quantity": qty
                                    })
                        
                        # Display Totals and Payment Links
                        st.markdown("---")
                        st.subheader("Your Bill Summary")
                        uploader_phone = group_bill_data["uploader"]
                        uploader_name = next((m["name"] for m in all_members if m["phone"] == uploader_phone), uploader_phone)
                        uploader_upi = next((m["upi_id"] for m in all_members if m["phone"] == uploader_phone), "")
                        
                        if user_phone != uploader_phone:
                            user_total = user_totals[user_phone]["amount"]
                            st.write(f"**Your Total: ₹{user_total:.2f}**")
                            st.write("Items:")
                            for item in user_totals[user_phone]["items"]:
                                st.write(f"- {item['name']} (Qty: {item['quantity']}): ₹{item['cost']:.2f}")
                            st.write(f"Tax Contribution: ₹{tax_per_person:.2f}")
                            
                            if uploader_upi:
                                upi_link = generate_upi_link(uploader_upi, uploader_name, user_total)
                                st.markdown(f"[Pay ₹{user_total:.2f} to {uploader_name}]({upi_link}) *(Open in UPI app)*")
                            else:
                                st.warning(f"{uploader_name} has not set a UPI ID.")
                        else:
                            st.write("You paid the bill. Here’s what others owe you:")
                            for member in all_members:
                                if member["phone"] != uploader_phone:
                                    member_total = user_totals[member["phone"]]["amount"]
                                    st.write(f"{member['name']}: ₹{member_total:.2f}")