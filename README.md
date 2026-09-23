# Cinema E-Booking System

The database is hosted on MongoDB Atlas ('cinema_db' database, 'movies collection')
Because the cloud database is already populated, team members do not need to run the seeding script unless they want to reset or update the database

Connect using MONGO_URI connection string (Carson's is already there and working by default). If you want to seed your own movie database, you will have to edit the .env file with your own MONGO_URI and API key so we don't hit data limits overusing a single API key.

Query the movies collection directly
 - ex: movies = list(db["movies"].find({}, {"_id": 0})) # fetches all movies from the database you can use for your API routes
Every movie comes with details needed, as seen in 'models.py'.

# 1. Backend Setup & Dependencies
Go to the 'backend' folder and install dependencies:
cd backend
python -m pip install -r requirements.txt