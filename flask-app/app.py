# backend.py

import random
from datetime import datetime

# Add this import at the beginning of your backend.py
from bson import ObjectId
from flask import Flask, jsonify, request, session
from flask_bcrypt import Bcrypt
from flask_cors import CORS
from flask_pymongo import PyMongo

app = Flask(__name__)
CORS(app)
app.config["MONGO_URI"] = (
    "mongodb://mongo:27017/csvdb"  # 'mongo' is the hostname of the MongoDB container
)

app.config["SECRET_KEY"] = "dev"
bcrypt = Bcrypt(app)

mongo = PyMongo(app)


@app.route("/getEmployee", methods=["GET"])
def get_employee():
    employees = list(mongo.db.csvdata.find({}, {"_id": 0}))  # Exclude _id field
    return jsonify(employees)


@app.route("/upload", methods=["POST"])
def upload_csv():
    try:
        csv_file = request.files["file"]
        choice = request.form.get("choice")

        if not csv_file or not choice:
            return jsonify({"error": "Invalid request"}), 400

        csv_content = csv_file.read().decode("utf-8")
        parsed_data = parse_csv_data(csv_content)

        if choice == "Set":
            # Check for duplicates and insert distinct details in MongoDB
            for row in parsed_data["data"]:
                name, location = row[0], row[1]
                existing_entry = mongo.db.csvdata.find_one(
                    {"name": name, "location": location}
                )

                if not existing_entry:
                    mongo.db.csvdata.insert_one({"name": name, "location": location})

        return jsonify({"message": "CSV data uploaded successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def parse_csv_data(csv_content):
    rows = csv_content.split("\n")
    header = rows[0].split(",")
    data = [row.split(",") for row in rows[1:]]
    return {"header": header, "data": data}


@app.route("/getLocations", methods=["GET"])
def get_locations():
    distinct_locations = list(mongo.db.csvdata.distinct("location"))
    return jsonify(distinct_locations)


@app.route("/chooseAndStoreEmployees", methods=["POST"])
def choose_and_store_employees():
    try:
        request_data = request.json
        user_name = str(request_data.get("userName", "admin"))
        location = request_data.get("location")
        num_employees_to_choose = int(request_data.get("numEmployeesToChoose", 1))

        if not user_name or not location or num_employees_to_choose <= 0:
            return (
                jsonify(
                    {
                        "error": "Invalid request. User name, location, or number of employees to choose is missing or invalid"
                    }
                ),
                400,
            )

        # Check if the user has already chosen for the current quarter and location
        current_quarter_start = datetime.now().replace(
            month=((datetime.now().month - 1) // 3) * 3 + 1,
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        existing_entry = mongo.db.networkingTool.find_one(
            {
                "userName": user_name,
                "location": location,
                "quarterStart": current_quarter_start,
            }
        )

        if existing_entry:
            return (
                jsonify(
                    {"message": "You have already chosen for this quarter and location"}
                ),
                200,
            )

        # Fetch existing employees for the specified location
        existing_employees = list(mongo.db.csvdata.find({"location": location}))

        if not existing_employees:
            return (
                jsonify(
                    {"error": f"No existing employees for the location: {location}"}
                ),
                404,
            )

        # Randomly choose specified number of existing employees
        chosen_employees = random.sample(
            existing_employees, min(num_employees_to_choose, len(existing_employees))
        )

        # Store the chosen employees along with user details in the new database
        store_chosen_employees(user_name, location, chosen_employees)

        return jsonify(
            [
                {
                    "userName": user_name,
                    "location": location,
                    "employee": employee["name"],
                    "quarterStart": current_quarter_start,
                }
                for employee in chosen_employees
            ]
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


def store_chosen_employees(user_name, location, chosen_employees):
    user_data_list = []

    # Get the start of the current quarter
    current_quarter_start = datetime.now().replace(
        month=((datetime.now().month - 1) // 3) * 3 + 1,
        day=1,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )

    for employee in chosen_employees:
        user_data = {
            "userName": user_name,
            "location": location,
            "employee": employee["name"],
            "quarterStart": current_quarter_start,
        }
        user_data_list.append(user_data)

    mongo.db.networkingTool.insert_many(user_data_list)


@app.route("/getListedEmployee", methods=["GET"])
def get_listed_employee():
    try:
        selected_quarter = request.args.get("quarter")

        if not selected_quarter:
            return jsonify({"error": "Invalid request. Quarter is missing"}), 400

        # Convert the selected quarter to datetime for comparison
        selected_quarter_date = datetime.strptime(selected_quarter, "%Y-%m-%d")

        # Fetch and filter data from networkingTool collection based on the selected quarter
        listed_employees = list(
            mongo.db.networkingTool.find(
                {"quarterStart": selected_quarter_date}, {"_id": 0}
            )
        )

        return jsonify(listed_employees)

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/getDistinctQuarters", methods=["GET"])
def get_distinct_quarters():
    distinct_quarters = list(mongo.db.networkingTool.distinct("quarterStart"))
    formatted_quarters = [quarter.strftime("%Y-%m-%d") for quarter in distinct_quarters]
    return jsonify(formatted_quarters)


@app.route("/deleteAllNetworking", methods=["DELETE"])
def delete_all_documents_networking():
    try:
        result = mongo.db.networkingTool.delete_many({})

        return (
            jsonify(
                {
                    "message": f"Deleted {result.deleted_count} documents from 'networkingTool' collection"
                }
            ),
            200,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/deleteAll", methods=["DELETE"])
def delete_all_documents():
    try:
        result = mongo.db.csvdata.delete_many({})

        return (
            jsonify(
                {
                    "message": f"Deleted {result.deleted_count} documents from 'csvdata' collection"
                }
            ),
            200,
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/updateEmployee", methods=["POST"])
def update_employee():
    try:
        request_data = request.json
        location = request_data.get("location")
        old_name = request_data.get("oldName")
        new_name = request_data.get("newName")

        if not location or not old_name or not new_name:
            return (
                jsonify(
                    {
                        "error": "Invalid request. Location, oldName, or newName is missing"
                    }
                ),
                400,
            )

        # Update entry in "csvdata" collection
        mongo.db.csvdata.update_one(
            {"location": location, "name": old_name}, {"$set": {"name": new_name}}
        )

        # Update entry in "networkingTool" collection
        mongo.db.networkingTool.update_many(
            {"location": location, "employee": old_name},
            {"$set": {"employee": new_name}},
        )

        return jsonify({"message": "Employee updated successfully"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/deleteByUsernameAndLocation", methods=["DELETE"])
def delete_by_username_and_location():
    try:
        request_data = request.json
        username = request_data.get("username")
        location = request_data.get("location")

        if not username or not location:
            return (
                jsonify({"error": "Invalid request. Username or location is missing"}),
                400,
            )

        # Delete entry in "networkingTool" collection
        result_networking = mongo.db.networkingTool.delete_many(
            {"userName": username, "location": location}
        )

        # Delete entry in "csvdata" collection
        result_csvdata = mongo.db.csvdata.delete_many(
            {"name": username, "location": location}
        )

        return (
            jsonify(
                {
                    "message": f"Deleted {result_networking.deleted_count} documents from 'networkingTool' collection and {result_csvdata.deleted_count} documents from 'csvdata' collection for username: {username} and location: {location}"
                }
            ),
            200,
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# @app.route("/signup", methods=["POST"])
# def signup():
#     try:
#         request_data = request.json
#         username = request_data.get("username")
#         password = request_data.get("password")

#         if not username or not password:
#             return (
#                 jsonify({"error": "Invalid request. Username or password is missing"}),
#                 400,
#             )

#         # Hash the password before storing it in the database
#         hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")

#         # Check if the username already exists
#         existing_user = mongo.db.users.find_one({"username": username})
#         if existing_user:
#             return jsonify({"error": "Username already exists"}), 409

#         # Store user information in the database
#         user_data = {"username": username, "password": hashed_password}
#         mongo.db.users.insert_one(user_data)

#         return jsonify({"message": "User registered successfully"}), 201

#     except Exception as e:
#         return jsonify({"error": str(e)}), 500


# Signup endpoint with Full Name
@app.route("/signup", methods=["POST"])
def signup():
    try:
        request_data = request.json
        username = request_data.get("username")
        password = request_data.get("password")
        full_name = request_data.get("fullName")  # Added Full Name

        if not username or not password or not full_name:
            return (
                jsonify(
                    {
                        "error": "Invalid request. Username, password, or Full Name is missing"
                    }
                ),
                400,
            )

        # Hash the password before storing it in the database
        hashed_password = bcrypt.generate_password_hash(password).decode("utf-8")

        # Check if the username already exists
        existing_user = mongo.db.users.find_one({"username": username})
        if existing_user:
            return jsonify({"error": "Username already exists"}), 409

        # Store user information in the database with Full Name
        user_data = {
            "username": username,
            "password": hashed_password,
            "fullName": full_name,
        }
        mongo.db.users.insert_one(user_data)

        return jsonify({"message": "User registered successfully"}), 201

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Login endpoint
@app.route("/login", methods=["POST"])
def login():
    try:
        request_data = request.json
        username = request_data.get("username")
        password = request_data.get("password")

        if not username or not password:
            return (
                jsonify({"error": "Invalid request. Username or password is missing"}),
                400,
            )

        # Check if the username exists
        user_data = mongo.db.users.find_one({"username": username})
        if not user_data:
            return jsonify({"error": "Invalid username or password"}), 401

        # Check if the password is correct
        if bcrypt.check_password_hash(user_data["password"], password):
            # Store user information in session for subsequent requests
            session["user_id"] = str(user_data["_id"])
            return jsonify({"message": "Login successful"}), 200
        else:
            return jsonify({"error": "Invalid username or password"}), 401

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# Logout endpoint
@app.route("/logout", methods=["POST"])
def logout():
    try:
        # Clear user information from session
        session.clear()
        return jsonify({"message": "Logout successful"}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/get_fullname", methods=["POST"])
def get_fullname():
    try:
        request_data = request.json
        username = request_data.get("username")

        if not username:
            return jsonify({"error": "Invalid request. Username is missing"}), 400

        # Check if the username exists
        user_data = mongo.db.users.find_one({"username": username})
        if user_data:
            full_name = user_data.get("fullName", "")
            return jsonify({"fullName": full_name}), 200
        else:
            return jsonify({"error": "User not found"}), 404

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
