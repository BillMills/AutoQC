import util.main as main
import sqlite3, pandas
import util.dbutils as dbutils

def query2df(meta, filter, tablename, database='iquod.db'):
    '''
    meta: list of strings of metadata to extract
    filter: string describing WHERE filter for SQL query, such as:
        'uid==1234'
        'cruise!=99 and month==10' etc
    tablename: sql table to extract from
    database: filename of database file

    return a dataframe with columns for every QC test plus specified metadata.
    also parses out truth if requested in the metadata list
    '''

    # get qc tests
    testNames = main.importQC('qctests')

    # connect to database
    conn = sqlite3.connect(database, isolation_level=None)
    cur = conn.cursor()

    # extract matrix of test results into a dataframe
    query = 'SELECT '
    if len(meta) > 0:
        query += ','.join(meta) + ','
    query += ','.join(testNames) + ' FROM ' + tablename
    if filter:
        query += ' WHERE ' + filter
    cur.execute(query)
    rawresults = cur.fetchall()
    df = pandas.DataFrame(rawresults).astype('str')
    df.columns = meta + testNames
    for t in testNames:
        df[[t]] = df[[t]].apply(dbutils.parse)

    # deal with truth data if present
    # column 'leveltruth' will persist per-level truth,
    # while 'Truth' summarizes by or'ing all levels together
    if 'truth' in meta:
        def unpack_truth(results):
            return results.apply(dbutils.unpack_qc)
        truth = df[['truth']].apply(unpack_truth).values.tolist()
        df = df.assign(leveltruth=pandas.Series(truth))
        df[['truth']] = df[['truth']].apply(dbutils.parse_truth)

    return df

def why_flag(uid, tests, tablename, database='iquod.db'):
    '''
    uid: int uid of profile in question
    tests: list of test names or combinations of tests joind by &
    tablename: sql table to extract from
    database: filename of database file

    determine which tests caused profile to be flagged.
    '''

    df = query2df([], 'uid='+str(uid), tablename, database)

    triggers = []
    for test in tests:
        qctests = test.split('&')
        flag = True
        for qctest in qctests:
            flag = flag & df.ix[0][qctest]
        if flag:
          triggers.append(test)

    return triggers

def construct_discrim(tests):
    '''
    tests: list of test names or combinations of tests joind by &

    return a function that accepts a qc database row as an argument and
    evaluates the qc assessment described by the 'tests' list
    '''

    def e(row):
        result = False
        for t in tests:
            qcs = t.split('&')
            term = True
            for qc in qcs:
                term = term and row[qc]
            result = result or term
        return result

    return e

def append_category(tests, tablename, database='iquod.db'):
    '''
    tests: list of test names or combinations of tests joind by &
    tablename: sql table to extract from
    database: filename of database file

    add a column 'category' to a qc table that indicates whether a profile is correctly or incorrectly flagged by
    the tests array from an analyze-results or catchall output, encoded as:
    0 == true positive
    1 == true negative
    2 == false positive
    3 == false negative
    '''

    # extract dataframe and apply discriminator
    df = query2df(['truth', 'uid'], '', tablename, database)
    discriminator = construct_discrim(tests)
    df['qc'] = df.apply(discriminator, axis=1)

    # create empty 'category' column in db
    conn = sqlite3.connect(database, isolation_level=None)
    cur = conn.cursor()
    query = 'ALTER TABLE ' + tablename + ' ADD category integer;'
    cur.execute(query)

    # write results to database
    def update_db(row):
        if row['qc'] and row['truth']:
            category = 0
        elif not row['qc'] and not row['truth']:
            category = 1
        elif row['qc'] and not row['truth']:
            category = 2
        elif not row['qc'] and row['truth']:
            category = 3
        query = 'UPDATE ' + tablename +  ' SET category = ' + str(category) + ' WHERE uid=' + str(row['uid'])
        cur.execute(query)
    df.apply(update_db, axis=1)

def dump_row(uid, table, database='iquod.db'):
    '''
    print all database keys and values for uid
    '''

    # extract and parse row
    conn = sqlite3.connect(database, isolation_level=None)
    cur = conn.cursor()
    query = 'SELECT * FROM ' + table +' WHERE uid=' + str(uid)
    cur.execute(query)
    rawresults = cur.fetchall()
    df = pandas.DataFrame(rawresults).astype('str')
    df.columns = [description[0] for description in cur.description]
    testNames = main.importQC('qctests')
    testNames = [t.lower() for t in testNames]
    for t in testNames:
        df[[t]] = df[[t]].apply(dbutils.parse)
    df[['truth']] = df[['truth']].apply(dbutils.parse_truth)

    for col in list(df):
        print col, ':', df.ix[0][col]
