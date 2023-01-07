from flask import Flask, redirect, url_for, render_template, request, jsonify, make_response
import cx_Oracle
import pandas as pd

#Starting Flask application
app = Flask(__name__)

# Defining variables for tree page
table_dict = dict()
schema_name = list()
join_query_list = list()

@app.route('/tree/get_columns', methods=['POST'])
def get_columns():
    
    cols_available = list() 

    # Fetching tables selected, dynamically creating columns selected dropdown
    tabs_selected = request.get_json()
    for tab in tabs_selected:
        cols_available = cols_available + [f'{col} - {tab}' for col in table_dict[f'{tab}']] 
    response = make_response(jsonify(cols_available), 200)

    return response

@app.route('/tree/get_join_query', methods = ['POST'])
def getjoinquery():

    # Fetching the join queries, putting them in a list
    join_query_list.append(request.get_json())

    if join_query_list[-2]:
        return join_query_list[-2]
    else:
        return None

#Creating ODBC page 
@app.route('/', methods=['GET', 'POST'])
def ODBC():

    error = None

    #Let the form be submitted
    if request.method == 'POST':
        try:
            column_list = list()
            #if connection works, we redirect to tree page
            global connection
            connection = cx_Oracle.connect(
            user=f"{request.form['username']}",
            password=f"{request.form['password']}",
            dsn=f"localhost/{request.form['databasename']}")
            global cursor
            # connection = cx_Oracle.connect(f"oe/")
            cursor = connection.cursor()

            # Fetching schema name
            schema_name.append(request.form['databasename'])

            # Fetching table list, column list
            for item in list(cursor.execute('SELECT DISTINCT table_name FROM USER_TAB_COLUMNS')):
                for item2 in list(cursor.execute(f"SELECT column_name FROM USER_TAB_COLUMNS WHERE table_name = '{item[0]}'")):
                    column_list.append(item2[0])
                table_dict[f'{item[0]}'] = column_list
                column_list = list()
            print(table_dict)

            return redirect(url_for('tree'))

        except:
            # If connection doesn't work, we include the error message
            error = 'Invalid Credentials. Please try again.'  

    return render_template('index.html', error=error)

# Creating the tree page
@app.route('/tree', methods=['GET','POST'])
def tree():

    queries = list()
    error2 = None
    dfs_html = list()

    # Let the form be submitted
    if request.method == 'POST':

        # Getting the join query - finding out if a join statement already exists
        try:
            join_query = getjoinquery()
        except:
            join_query = None
        
        col_tabs = dict()

        # Getting the form data
        tabs_selected = request.form.getlist('Tables')
        cols_and_tabs = request.form.getlist('Columns')
        for col_and_tab in cols_and_tabs:
            col_tabs[col_and_tab.split(' - ')[0]] = col_and_tab.split(' - ')[1]
        result_dict = request.form.to_dict()
        join_tables = result_dict.pop('Join_Tables', None)
        join_method = result_dict.pop('Joins', None)

        # Getting the queries for columns
        if join_tables == 'None' or join_method == 'None':

            for k,v in col_tabs.items():
                queries.append(f"SELECT {k} FROM {v}")
            
        # If join is specified
        elif join_method != 'None' and join_tables != 'None':

            # If there is no join query stored, append has not been selected even once.            
            if join_query == None:

                j_tables = [join_tables.split()[0], join_tables.split()[2]]
                c_match = None
                for col in table_dict[f'{j_tables[0]}']:
                    if col in table_dict[f'{j_tables[1]}']:
                        c_match = col
                for tab in tabs_selected:
                    if tab not in j_tables:
                        for k,v in col_tabs.items():
                            if v == tab:
                                queries.append(f"SELECT {k} FROM {tab}")            
                queries.append(f"SELECT * FROM {j_tables[0]} {join_method} {j_tables[1]} ON {j_tables[0]}.{c_match}={j_tables[1]}.{c_match}")

            else:
                c_match = None
                join_query = join_query.replace('"' , '')
                old_table = [table for table in table_dict.keys() if table in join_query][0]
                new_table = join_tables.split()[2]
                old_table_df = pd.read_sql(join_query, con=connection)
                for col in table_dict[f'{new_table}']:
                    if col in [c for c in old_table_df.columns]:
                        c_match = col
                queries.append(f"{join_query} {join_method} {new_table} ON {new_table}.{c_match}={old_table}.{c_match}")

        # If join is not specified properly
        else:
            error2 = 'Please specify join tables AND join method'

        # Executing the queries
        try:
            dfs = [pd.read_sql(query, con=connection) for query in queries]   
            # Converting the pandas dfs to a list of html tables
            dfs_html = [df.to_html() for df in dfs]

        except:
            dfs_html = ['SQL Execution failed']  

    return render_template('tree_extends.html', schemaname=schema_name, table_dict=table_dict, error2=error2, queries=queries, dfs_html=dfs_html)

#Running the application
if __name__== "__main__":
    app.run()