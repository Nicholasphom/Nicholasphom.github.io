import requests
import pandas as pd
import io
import os
import mysql.connector
import hashlib
import pandas as pd
import numpy as np
import json 

def lambda_handler(event, context):
    # TODO implement
    
    try:
        earthquake_url = 'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/2.5_day.csv'
        s=requests.get(earthquake_url).content
        earthquake_df = pd.read_csv(io.StringIO(s.decode('utf-8')))
        earthquake_df = create_hash_column(earthquake_df)
        earthquake_df = earthquake_df.fillna(0.00)
        mysql_column_types = convert_pandas_to_mysql_types(earthquake_df)
        connection = mysql.connector.connect(
            host=os.environ["MYSQL_ENDPOINT"],
            user=os.environ["MYSQL_USER"],
            password=os.environ["MYSQL_PASS"]
        )
        cursor = connection.cursor()
        hash_sql = cursor.execute("select hash_column from portfolio.earthquake_table")
        hash_result = cursor.fetchall()
        hash_list = [row[0] for row in hash_result]
        upsert_earthquake_df =  earthquake_df[~earthquake_df['hash_column'].isin(hash_list)]
        upsert_earthquake_df = upsert_earthquake_df.fillna(0.00)
        insert_statment = create_insert_statments(mysql_column_types,"portfolio.earthquake_table")
        for index, row in upsert_earthquake_df.iterrows():
            values = [row[column] for column in mysql_column_types.keys()]
            #print(values)
            cursor.execute(insert_statment, values)
        cursor.commit()
        cursor.close()
        
        return {
            'statusCode': 200,
            'body': json.dumps(str(f"Uploaded {upsert_earthquake_df.shape[0]} Rows"))
            }
    except Exception as e:
        return {
            'statusCode': 404,
            'body': json.dumps(str(e))
            
        }
        
def create_hash_column(dataframe):
    """
    Create a hash column by combining all other columns in the DataFrame into a string
    and hashing it using SHA-256.

    Args:
        dataframe (pandas.DataFrame): The input DataFrame.

    Returns:
        pandas.DataFrame: The DataFrame with an additional 'hash_column' containing the hash values.
    """
    # Combine all columns into a single string
    combined_string = dataframe.apply(lambda row: ''.join(map(str, row)), axis=1)

    # Create a new column with the hash values
    dataframe['hash_column'] = combined_string.apply(lambda x: hashlib.sha256(x.encode()).hexdigest())

    return dataframe

def pandas_to_mysql_type(pandas_type):
    """
    Convert a Pandas data type to its MySQL equivalent.
    
    Args:
        pandas_type (str): The Pandas data type as a string.

    Returns:
        str: The MySQL data type as a string.
    """
    if pandas_type == 'object':
        return 'TEXT'
    elif pandas_type == 'int64':
        return 'INT'
    elif pandas_type == 'float64':
        return 'FLOAT'
    elif pandas_type == 'datetime64':
        return 'DATETIME'
    elif pandas_type == 'bool':
        return 'BOOL'
    else:
        # Handle other cases or raise an error for unsupported types.
        raise ValueError(f"Unsupported Pandas type: {pandas_type}")

def convert_pandas_to_mysql_types(dataframe):
    """
    Convert Pandas column types to MySQL data types for a DataFrame.

    Args:
        dataframe (pd.DataFrame): The Pandas DataFrame to convert.

    Returns:
        dict: A dictionary mapping column names to MySQL data types.
    """
    mysql_types = {}
    for column_name, dtype in dataframe.dtypes.items():
        mysql_type = pandas_to_mysql_type(dtype.name)
        mysql_types[column_name] = mysql_type
    return mysql_types

def create_insert_statments(mysql_column_types,table_name):
    columns = ', '.join(mysql_column_types.keys())
    placeholders = ', '.join(['%s'] * len(mysql_column_types))
    insert_sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"
    return insert_sql