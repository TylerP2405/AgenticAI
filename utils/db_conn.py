import psycopg2

class DatabaseUtil:

    def __init__(self, db_config):
        self.db_config = db_config
        try:
            self.connection = psycopg2.connect(**db_config) 
        except Exception as e:
            print(f"Error connecting to the database: {e}")
            self.connection = None

    def schema_details(self, schema_name):
        schema_context = ""    
        connection = self.connection
        cursor = connection.cursor()

        schema_context = f"Database Schema: {schema_name}\n"
        try:

            cursor.execute(("""
                SELECT table_name from information_schema.tables
                WHERE table_schema = %s;
            """), (schema_name,))
            tables_list = cursor.fetchall()

            for table in tables_list:
                table_name = table[0]
                schema_context = f"{schema_context}\nTable: {table_name}\n"

                cursor.execute(("""
                    SELECT column_name, data_type
                    FROM information_schema.columns
                    WHERE table_name = %s;
                """), (table_name,))
                columns_list = cursor.fetchall()

                for column in columns_list:
                    col_name = column[0]
                    col_dtype = column[1]
                    schema_context = f"{schema_context} Column: {col_name}, Data Type: {col_dtype}\n"

                cursor.execute(f"SELECT * FROM {schema_name}.{table_name} LIMIT 5")
                sample_data = cursor.fetchall()
                schema_context = f"{schema_context} Sample Data:\n"
                for row in sample_data:
                    schema_context = f"{schema_context}     {row}\n"
        except Exception as e:
            print(f"Error fetching schema detail: {e}")
            schema_context = f"Error fetching schema detail: {e}"
        finally:
            if cursor: cursor.close()
            if connection: connection.close()
        return schema_context


    def execute_sql(self, query):
        try:
            connection = self.connection
            cursor = connection.cursor()
            cursor.execute(query)
            res = cursor.fetchall()
            connection.commit()
            return str(res)
        except Exception as e:
            print(f"Error executing query: {e}")
            return None
        finally:
            if cursor: cursor.close()
            if connection: connection.close()

            
        


