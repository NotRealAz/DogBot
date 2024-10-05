import sqlite3
import os

class DB:
    def __init__(self):
        """
        Initializes the database by creating the tables if they don't exist already.
        """
        databases_folder = 'databases'
        if not os.path.exists(databases_folder):
            os.makedirs(databases_folder)
        self.conn = sqlite3.connect(os.path.join(databases_folder, 'database.db'))
        
        self.create_tables()

    def create_tables(self):
        """
        Creates the tables needed for the database.
        """
        with self.conn:
            self.conn.execute('''CREATE TABLE IF NOT EXISTS dogs (
                type TEXT NOT NULL,
                amount INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                guild_id TEXT NOT NULL,
                PRIMARY KEY (type, user_id, guild_id)
            );''')
            self.conn.execute('''CREATE TABLE IF NOT EXISTS server_config (
                catching_channel_id INTEGER NOT NULL,
                slow_catching_channel_id INTEGER NOT NULL,
                guild_id TEXT NOT NULL,
                PRIMARY KEY (catching_channel_id, slow_catching_channel_id, guild_id)
            );''')

    def catch_dog(self, type, user_id, guild_id, amount=1):
        """
        Adds a dog to the user's inventory or updates the amount if the dog already exists.
        Uses ON CONFLICT to avoid separate INSERT and UPDATE queries.
        """
        with self.conn:
            cursor = self.conn.execute(
                """INSERT INTO dogs (type, user_id, guild_id, amount) 
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(type, user_id, guild_id) 
                   DO UPDATE SET amount = amount + ?""",
                (type, user_id, guild_id, amount, amount)
            )
            return cursor.rowcount  # Return the number of affected rows

    def list_dogs(self, user_id, guild_id):
        """
        Returns all dogs for a user in a guild.
        """
        with self.conn:
            cursor = self.conn.execute(
                "SELECT type, amount FROM dogs WHERE user_id = ? AND guild_id = ?",
                (user_id, guild_id)
            )
            result = cursor.fetchall()
            return result if result else []  # Return an empty list if no dogs found
        
    def get_leaderboard(self, guild_id):
        """
        
        Returns the leaderboard for a specific guild.
        Returns the rarest dog and the top 15 users with the most dogs.

        [ Rarest dog in the database (guild based) ]
        
        [ amount dogs: User_ID ]

        """
        with self.conn:
            cursor = self.conn.execute(
                """SELECT type, SUM(amount) as total_amount 
                FROM dogs 
                WHERE guild_id = ? 
                GROUP BY type 
                ORDER BY total_amount ASC 
                LIMIT 1""",
                (guild_id,)
            )
            rarest_dog = cursor.fetchone()  # ('dog_type', total_amount)

            cursor = self.conn.execute(
                """SELECT user_id, SUM(amount) as total_amount 
                FROM dogs 
                WHERE guild_id = ? 
                GROUP BY user_id 
                ORDER BY total_amount DESC 
                LIMIT 15""",
                (guild_id,)
            )
            top_users = cursor.fetchall()
            
        return rarest_dog, top_users

    def update_server_config(self, catching_channel_id, slow_catching_channel_id, guild_id):
        """
        Updates the server's configuration.
        Uses ON CONFLICT to avoid separate INSERT and UPDATE queries.
        """
        with self.conn:
            cursor = self.conn.execute(
                """INSERT INTO server_config (catching_channel_id, slow_catching_channel_id, guild_id)
                   VALUES (?, ?, ?)
                   ON CONFLICT(catching_channel_id, slow_catching_channel_id, guild_id) 
                   DO UPDATE SET catching_channel_id = ?, slow_catching_channel_id = ?""",
                (catching_channel_id, slow_catching_channel_id, guild_id, catching_channel_id, slow_catching_channel_id)
            )
            return cursor.rowcount  # Return the number of affected rows

    def list_server_config(self, guild_id):
        """
        Returns the server's configuration for a guild.
        """
        with self.conn:
            cursor = self.conn.execute(
                "SELECT catching_channel_id, slow_catching_channel_id FROM server_config WHERE guild_id = ?",
                (guild_id,)
            )
            result = cursor.fetchone()
            return result if result else None  # Return None if no config found

    def __enter__(self):
        """
        Enter method for the context manager.
        """
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """
        Exit method for the context manager. Closes the connection.
        """
        self.conn.close()

    def __del__(self):
        """
        Ensures the database connection is closed when the DB instance is deleted.
        """
        self.conn.close()
