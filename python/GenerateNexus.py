#!/usr/bin/env python
##############################################################################
# Description:      Script to convert raw meshes data item to 3D hop format (nexus)
#
# Authors:          Oscar Martinez, NLeSC, o.rubi@esciencecenter.nl
#                   
#
# Created:          25.06.2015
# Last modified:    25.06.2015
#
# Changes:
##############################################################################

import shutil, time, os, utils, glob, subprocess, argparse, shlex, logging

CONVERTER_COMMAND = 'nxsbuild'
outputFormat = 'nxs'

def createNexus(cursor, itemId, nexusDir):
    
    # extract abspath using raw_data_item_id
    data_items, num_items = utils.fetchDataFromDB(
        cursor, "SELECT abs_path, item_id FROM RAW_DATA_ITEM WHERE " +
        "raw_data_item_id = %s", (itemId,))
    abspath, site_id = data_items[0]
    
    inputFiles = (glob.glob(abspath + '/*.ply') + glob.glob(abspath + '/*.PLY'))
    if len(inputFiles):
        inputFile = inputFiles[0]
    else:
        error('none PLY file was found.', abspath)
    
    if not os.path.isfile(inputFile):
        error('none PLY file was found.' , abspath)
         
    inputFileName = os.path.basename(inputFile)
    outputFileName = inputFileName + '.nxs'
    
    # extract inType & outFolder, create outFolder in non-existent
    inType, inKind, outFolder = extract_inType(abspath, site_id,nexusDir)
    if os.path.isfile(abspath):
        # input was a file -> raise IOError
        error('Database key absPath should define a directory, ' +
                      'file detected: ' + abspath, outFolder)
        # os.chdir(os.path.dirname(inFile))
    else:
        # input is already a directory
        os.chdir(abspath)

    # create the output folder
    os.system('mkdir -p ' + outFolder)
    
    # Run the nxsbuild in the docker container nxs in the docker-machine
    outputPath = os.path.join(outFolder, outputFileName)
    command = "nxsbuild " + inputFileName + " -o " + outputPath
    logging.info(command)
    os.system(command)

    if not os.path.isfile(outputPath):
        error('none Nexus file was generated (found in ' + outFolder +
                     ').', outFolder)

def extract_inType(abspath, site_id, nexusDir):
    '''
    Checks the type of the input file using the file location
    '''
    if abspath.count('/MESH/'):
        inType = utils.MESH_FT
    else:
        logging.error("Nexus converter should one be used on meshes")
        raise Exception("Nexus converter should one be used on meshes")
    
    if '/SITE/' in abspath:
        inKind = utils.SITE_FT
    elif '/BACK/' in abspath:
        inKind = utils.BG_FT
    else:
        logging.error('could not determine kind from abspath')
        raise Exception('Could not determine kind from abspath')
    
    if '/CURR/' in abspath:
        period = 'CURR'
    elif '/ARCH_REC/' in abspath:
        period = 'ARCH_REC'
    else:
        raise Exception('Could not determine period CURR/ARCH_REC')

    
    # define outFolder from potreeDir and inType
    if (inType == utils.MESH_FT and inKind == utils.SITE_FT):
        outFolder = os.path.join(os.path.abspath(nexusDir), utils.MESH_FT, inKind,
                                 period, 'S'+str(site_id),
                                 os.path.basename(os.path.normpath(abspath)))
    elif (inType == utils.MESH_FT and inKind == utils.BG_FT):
        outFolder = os.path.join(os.path.abspath(nexusDir), utils.MESH_FT, inKind,
                                 period, os.path.basename(os.path.normpath(abspath)))
    else:
        logging.error("Nexus converter should one be used on meshes")
        raise Exception("Nexus converter should one be used on meshes")
        
    # create outFolder if it does not exist yet
    if not os.path.isdir(outFolder):
        os.makedirs(outFolder)
    else:
        raise IOError('Output folder ' + outFolder + ' already exists, ' +
                      'please remove manually')
        # shutil.rmtree(outFolder)  # if we won't to force remove it
    return inType, inKind, outFolder

def error(errorMessage, outFolder):
     logging.error(errorMessage)
     logging.info('Removing %s ' % outFolder)
     shutil.rmtree(outFolder)
     raise Exception(errorMessage)
 
def run(opts):
    # Start logging
    logname = os.path.splitext(os.path.basename(__file__))[0] + '.log'
    utils.start_logging(filename=logname, level=opts.log)
    localtime = utils.getCurrentTimeAsAscii()
    t0 = time.time()
    msg = os.path.basename(__file__) + ' script starts at %s.' % localtime
    print msg
    logging.info(msg)
    # database connection
    connection, cursor = utils.connectToDB(opts.dbname, opts.dbuser,
                                           opts.dbpass, opts.dbhost,
                                           opts.dbport)
    
    if opts.itemid == '?':
        utils.listRawDataItems(cursor)
        return
    elif opts.itemid == '' or opts.itemid == '!':
        query = """
SELECT raw_data_item_id,abs_path
FROM RAW_DATA_ITEM JOIN ITEM USING (item_id) JOIN RAW_DATA_ITEM_MESH USING (raw_data_item_id) 
WHERE ply_abs_path is NOT NULL AND raw_data_item_id NOT IN (
          SELECT raw_data_item_id FROM NEXUS_DATA_ITEM_MESH)"""
        # Get the list of items that are not converted yet (we sort by background to have the background converted first)
        raw_data_items, num_raw_data_items = utils.fetchDataFromDB(cursor, query)
        for (rawDataItemId,absPath) in raw_data_items:
            if opts.itemid == '' :
                createNexus(cursor, rawDataItemId, opts.nexusDir)
            else:
                m = '\t'.join((str(rawDataItemId),absPath))
                print m
                logging.info(m)
                
    else:
        for rawDataItemId in opts.itemid.split(','):
            rows,num_rows = utils.fetchDataFromDB(cursor, 'SELECT * FROM RAW_DATA_ITEM JOIN ITEM USING (item_id) WHERE raw_data_item_id = %s', [int(rawDataItemId)])
            if num_rows == 0:
                logging.error('There is not a raw data item with id %d' % int(rawDataItemId))
                return
            createNexus(cursor, int(rawDataItemId), opts.nexusDir)

    # close DB connection
    utils.closeConnectionDB(connection, cursor)

    elapsed_time = time.time() - t0
    msg = 'Finished. Total elapsed time: %.02f seconds. See %s' % (elapsed_time, logname)
    print(msg)
    logging.info(msg)

def argument_parser():
# define argument menu
    description = "Generates the 3DHop data (nexus) for a raw data item (ONLY FOR meshes which have a related PLY file)"
    parser = argparse.ArgumentParser(description=description)

    # fill argument groups
    parser.add_argument('-i','--itemid',default='',
                       help='Comma-separated list of Meshes Raw Data Item Ids [default is to convert all raw meshes data items which have a PLY file and that do not have a related 3DHop data item] (with ? the available raw data items are listed, with ! the list of all the raw meshes data items with PLY and without any related 3DHop data item)',
                       type=str, required=False)
    parser.add_argument('-d', '--dbname', default=utils.DEFAULT_DB,
                        help='Postgres DB name [default ' + utils.DEFAULT_DB +
                        ']', action='store')
    parser.add_argument('-u', '--dbuser', default=utils.USERNAME,
                        help='DB user [default ' + utils.USERNAME +
                        ']', action='store')
    parser.add_argument('-p', '--dbpass', help='DB pass', action='store')
    parser.add_argument('-t', '--dbhost', help='DB host', action='store')
    parser.add_argument('-r', '--dbport', help='DB port', action='store')
    parser.add_argument('-o', '--nexusDir', default=utils.DEFAULT_NEXUS_DATA_DIR,
                        help='Nexus data directory [default ' +
                        utils.DEFAULT_NEXUS_DATA_DIR + ']', action='store')

    parser.add_argument('-l', '--log', help='Log level',
                        choices=utils.LOG_LEVELS_LIST,
                        default=utils.DEFAULT_LOG_LEVEL)
    return parser

if __name__ == "__main__":
    try:
        utils.checkSuperUser()
        run(utils.apply_argument_parser(argument_parser()))
    except Exception as e:
        print e
