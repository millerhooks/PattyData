#!/usr/bin/env python
################################################################################
#    Created by Oscar Martinez                                                 #
#    o.rubi@esciencecenter.nl                                                  #
################################################################################
import os, time, calendar, logging
import psycopg2
from osgeo import osr

# Python Module containing methods used in other scripts
PROPERTIES = {'administrator':('initials', 'list_participants'),
'site_context':('site_context', 'list_site_context'),
'site_interpretation':('site_interpretation', 'list_site_interpretation'),
'condition':('condition', 'list_object_condition'),
'object_type':('object_type', 'list_object_type'),
'object_interpretation':('object_interpretation', 'list_object_interpretation'),
'period':('period', 'list_object_period'),
'reliability':('reliability', 'list_reliability'),
'depression_type':('depression_type', 'list_depression_type'),
'decoration_type':('decoration_type', 'list_object_decoration_type'),
'depiction':('depiction', 'list_object_depiction'),
'material_type':('material_type', 'list_object_material_type'),
'material_subtype':('material_subtype', 'list_object_material_subtype'),
'material_technique':('material_technique', 'list_object_material_technique')}

PROPERTIES_ORDER = ['administrator', 'site_context', 'site_interpretation', 'condition', 'object_type',  
                    'object_interpretation', 'period', 'reliability', 'depression_type', 'decoration_type',
                    'depiction', 'material_type', 'material_subtype', 'material_technique']

DEFAULT_DB = 'vadb'
USERNAME = os.popen('whoami').read().replace('\n','')
# Folder tags for the file structure
RAW_FT = 'RAW'
OSG_FT = 'OSG'
POT_FT = 'POTREE'
PC_FT = 'PC'
MESH_FT = 'MESH'
PIC_FT = 'PICT'
BG_FT = 'BACK'
SITE_FT = 'SITE'
CURR_FT = 'CURR'
ARCREC_FT = 'ARCH_REC'
HIST_FT = 'HIST'
# Default data directories
DEFAULT_DATA_DIR = '/home/pattydat/DATA'
DEFAULT_RAW_DATA_DIR = DEFAULT_DATA_DIR + '/RAW' 
DEFAULT_OSG_DATA_DIR = DEFAULT_DATA_DIR + '/OSG'
DEFAULT_POTREE_DATA_DIR = DEFAULT_DATA_DIR + '/POTREE'
BOUNDINGS_XML_RELATIVE = 'BOUND/volumes.prototype.xml'
ITEM_ID_BACKGROUND = -1
ITEM_OBJECT_NUMBER_ITEM = -1
DEFAULT_PROTO = 'Bounding Box'
DEFAULT_Z = -140
DEFAULT_BACKGROUND = 'DRIVE_1_V3'
DEFAULT_BACKGROUND_FOLDER = DEFAULT_RAW_DATA_DIR + '/' + PC_FT + '/' + BG_FT + '/' + DEFAULT_BACKGROUND
SRID = 32633
DEFAULT_CAMERA_PREFIX = 'DEF_CAM_'
USER_CAMERA = 'SITE_'

# define global LOG variables
DEFAULT_LOG_LEVEL = 'debug'
LOG_LEVELS = {'debug': logging.DEBUG,
              'info': logging.INFO,
              'warning': logging.WARNING,
              'error': logging.ERROR,
              'critical': logging.CRITICAL}
LOG_FORMAT = '%(asctime)-15s %(message)s'
LOG_FILENAME = '/tmp/patty.log'

#Ouput Formats
LAS = 'LAS'
LAZ = 'LAZ'

def getLastModification(absPath, initialLMTime = None):
    """
    Get the last modification time of the provided path. 
    The returned values is the number of seconds since the epoch given in time module
    So, it is the UnixTime
    """
    lastModifiedTime = initialLMTime
    if os.path.isfile(absPath):
        t = os.path.getmtime(absPath)
        if lastModifiedTime == None or t > lastModifiedTime:
            lastModifiedTime = t
    elif os.path.isdir(absPath):
        # it is a dir
        for element in os.listdir(absPath):
            elementPath = absPath + '/' + element
            t = os.path.getmtime(elementPath)
            if lastModifiedTime == None or t > lastModifiedTime:
                lastModifiedTime = t
            if os.path.isdir(elementPath):
                t = getLastModification(elementPath, lastModifiedTime)
                if lastModifiedTime == None or t > lastModifiedTime:
                    lastModifiedTime = t
    return lastModifiedTime

def getCurrentTime(t = None):
    """
    Get current localUnixTime if t is None. Convert t to localUnixTime. 
    t is seconds since the epoch given by module time (GMT/UTC)
    localUnixTime = UnixTime + 7200 [or 3600]
    """
    return calendar.timegm(time.localtime(t))
    
def getCurrentTimeAsAscii():
    """ Return the current local time in ASCII. Use it if you want a prettyly 
        formatted time
    """    
    return time.asctime( time.localtime(time.time()) )
    
def postgresConnectString(dbName = None, userName= None, password = None, dbHost = None, dbPort = None, cline = False):
    connString=''
    if cline:    
        if dbName != None and dbName != '':
            connString += " " + dbName
        if userName != None and userName != '':
            connString += " -U " + userName
        if password != None and password != '':
            os.environ['PGPASSWORD'] = password
        if dbHost != None and dbHost != '':
            connString += " -h " + dbHost
        if dbPort != None and dbPort != '':
            connString += " -p " + dbPort
    else:
        if dbName != None and dbName != '':
            connString += " dbname=" + dbName
        if userName != None and userName != '':
            connString += " user=" + userName
        if password != None and password != '':
            connString += " password=" + password
        if dbHost != None and dbHost != '':
            connString += " host=" + dbHost
        if dbPort != None and dbPort != '':
            connString += " port=" + dbPort
    return connString

def connectToDB(dbName = None, userName= None, password = None, dbHost = None, dbPort = None):
    """ Connects to a specified DB and returns connection and cursor objects
    """       
    # Start DB connection
    try: 
        connection = psycopg2.connect(postgresConnectString(dbName, userName, password, dbHost, dbPort, False))
        
    except Exception, E:
        err_msg = 'Cannot connect to %s DB.'% dbName
        print(err_msg)
        logging.error((err_msg, "; %s: %s" % (E.__class__.__name__, E)))
        raise
        
    msg = 'Successful connection to %s DB.'%dbName
    print msg
    logging.debug(msg)
    
    # if the connection succeeded get a cursor    
    cursor = connection.cursor()
        
    return connection, cursor
    
def closeConnectionDB(connection, cursor):
    """ Closes a connection to a DB given the connection and cursor objects
    """      
    cursor.close()
    connection.close()    
    
    msg = 'Connection to the DB is closed.'
    print msg
    logging.debug(msg)
    
    return    

def countElementsTable(cursor, table):
    """ Checks and returns the number of elements in a table"""    
    num_elements= 0
    
    count_query = "SELECT COUNT(*) FROM " + table
    dbExecute(cursor, count_query)
    
    num_elements = cursor.fetchone()
    
    return num_elements
    
def fetchDataFromDB(cursor, fetch_query):
    """ Fetches data from a DB, given the sursor object and the fetch query
        Return the fetched data items and their number
    """ 
    data_items = []
    
    try:
        dbExecute(cursor, fetch_query, None, True)
    except Exception, E:
        err_msg = "Cannot execute the SQL query: %s" % fetch_query
        print(err_msg)
        logging.error((err_msg, "; %s: %s" % (E.__class__.__name__, E)))
        raise
    
    data_items = cursor.fetchall()
    
    num_items = cursor.rowcount
    msg = 'Retrived %s data_items.'%num_items
    print msg
    logging.debug(msg)

    return data_items, num_items    
    
def dbExecute(cursor, query, queryArgs = None, mogrify = True):
    if queryArgs == None:
        if mogrify:
            logging.debug(cursor.mogrify(query))
        cursor.execute(query)
    else:
        if mogrify:
            logging.debug(cursor.mogrify(query, queryArgs))
        cursor.execute(query, queryArgs)
    cursor.connection.commit()

def start_logging(filename=LOG_FILENAME, level=DEFAULT_LOG_LEVEL):
    "Start logging with given filename and level."
    logging.basicConfig(filename=filename, level=LOG_LEVELS[level],
                        format=LOG_FORMAT)
    logger = logging.getLogger(__name__)
    return logger

def readSRID(lasHeader):
    osrs = osr.SpatialReference()
    osrs.SetFromUserInput(lasHeader.get_srs().get_wkt())
    #osrs.AutoIdentifyEPSG()
    return osrs.GetAttrValue( 'AUTHORITY', 1 )
