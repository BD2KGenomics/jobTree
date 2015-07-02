#!/usr/bin/env python
"""Tests the scriptTree jobTree-script compiler.
"""

import unittest
import os
import random
from uuid import uuid4
import logging
import shutil
import tempfile
from jobTree.target import Target
from jobTree.lib.bioio import getLogLevelString
from jobTree.common import parasolIsInstalled, gridEngineIsInstalled
from jobTree.test.sort.lib import merge, sort, copySubRangeOfFile, getMidPoint
from jobTree.test import JobTreeTest

log = logging.getLogger(__name__)

class SortTest(JobTreeTest):
    
    def setUp(self):
        super( SortTest, self).setUp()
        self.jobTreeDir = os.path.join(os.getcwd(), "testJobTree") #A directory for the job tree to be created in
        self.tempDir = tempfile.mkdtemp(prefix="tempDir", dir=os.getcwd())
        self.testNo = 5
        
    def tearDown(self):
        super( SortTest, self).tearDown( )
        if os.path.exists(self.jobTreeDir):
            shutil.rmtree(self.jobTreeDir)
        if os.path.exists(self.tempDir):
            shutil.rmtree(self.tempDir)
    
    def jobTreeSortTest(self, testNo=1, batchSystem="singleMachine", jobStore='file', 
                lines=10000, maxLineLength=10, N=10000):
        """
        Tests jobTree by sorting a file in parallel.
        """
        for test in xrange(testNo):
            options = Target.Runner.getDefaultOptions()
            
            #Job tree
            if jobStore == 'file':
                options.jobTree = self.jobTreeDir
            else:
                options.jobTree = jobStore

            # Specify options
            options.logLevel = getLogLevelString()
            options.retryCount = 32
            
            #Make the file to sort
            tempSortFile = os.path.join(self.tempDir, "fileToSort.txt")
            makeFileToSort(tempSortFile, lines=lines, maxLineLength=maxLineLength)
            
            # First make our own sorted version
            with open(tempSortFile, 'r') as fileHandle:
                l = fileHandle.readlines()
                l.sort()
            
            # Run the jobTree
            firstTarget = Target.wrapTargetFn(setup, tempSortFile, N)
            i = Target.Runner.startJobTree(firstTarget, options)
            
            #There should be no failed jobs
            self.assertEquals(i, 0)
            
            # Now check the file is properly sorted..
            # Now get the sorted file
            with open(tempSortFile, 'r') as fileHandle:
                l2 = fileHandle.readlines()
                checkEqual(l, l2)

    def testJobTreeSortOnAWS(self):
        """Tests scriptTree/jobTree by sorting a file in parallel.
        """
        return
        self.jobTreeSortTest(jobStore="aws:us-west-2:sort-test-%s" % uuid4(),
                      lines=100, N=100)

    def testJobTreeSort(self):
        """Tests scriptTree/jobTree by sorting a file in parallel.
        """
        self.jobTreeSortTest()

    # The following functions test the functions in the test!
    
    def testSort(self):
        for test in xrange(self.testNo):
            tempFile1 = os.path.join(self.tempDir, "fileToSort.txt")
            makeFileToSort(tempFile1)
            lines1 = loadFile(tempFile1)
            lines1.sort()
            sort(tempFile1)
            with open(tempFile1, 'r') as f:
                lines2 = f.readlines()
            checkEqual(lines1, lines2)

    def testMerge(self):
        for test in xrange(self.testNo):
            tempFile1 = os.path.join(self.tempDir, "fileToSort1.txt")
            tempFile2 = os.path.join(self.tempDir, "fileToSort2.txt")
            tempFile3 = os.path.join(self.tempDir, "mergedFile.txt")
            makeFileToSort(tempFile1)
            makeFileToSort(tempFile2)
            sort(tempFile1)
            sort(tempFile2)
            with open(tempFile3, 'w') as fileHandle:
                with open(tempFile1) as tempFileHandle1:
                    with open(tempFile2) as tempFileHandle2:
                        merge(tempFileHandle1, tempFileHandle2, fileHandle)
            lines1 = loadFile(tempFile1) + loadFile(tempFile2)
            lines1.sort()
            with open(tempFile3, 'r') as f:
                lines2 = f.readlines()
            checkEqual(lines1, lines2)

    def testCopySubRangeOfFile(self):
        for test in xrange(self.testNo):
            tempFile = os.path.join(self.tempDir, "fileToSort1.txt")
            outputFile = os.path.join(self.tempDir, "outputFileToSort1.txt")
            makeFileToSort(tempFile)
            fileSize = os.path.getsize(tempFile)
            assert fileSize > 0
            fileStart = random.choice(xrange(0, fileSize))
            fileEnd = random.choice(xrange(fileStart, fileSize))
            fileHandle = open(outputFile, 'w')
            copySubRangeOfFile(tempFile, fileStart, fileEnd, fileHandle)
            fileHandle.close()
            l = open(outputFile, 'r').read()
            l2 = open(tempFile, 'r').read()[fileStart:fileEnd]
            checkEqual(l, l2)

    def testGetMidPoint(self):
        for test in xrange(self.testNo):
            tempFile = os.path.join(self.tempDir, "fileToSort.txt")
            makeFileToSort(tempFile)
            l = open(tempFile, 'r').read()
            fileSize = os.path.getsize(tempFile)
            midPoint = getMidPoint(tempFile, 0, fileSize)
            print "the mid point is %i of a file of %i bytes" % (midPoint, fileSize)
            assert midPoint < fileSize
            assert l[midPoint] == '\n'
            assert midPoint >= 0

###########################################
#Functions to generate file store and check result is okay
###########################################  
          
def checkEqual(i, j):
    if i != j:
        print "lengths", len(i), len(j)
        print "true", i
        print "false", j
    assert i == j

def loadFile(file):
    with open(file, 'r') as fileHandle:
        return fileHandle.readlines()

def getRandomLine(maxLineLength):
    return "".join([random.choice(['a', 'c', 't', 'g', "A", "C", "G", "T", "N", "X", "Y", "Z"]) for i in
                    xrange(maxLineLength)]) + "\n"

def makeFileToSort(fileName, lines=10, maxLineLength=10):
    with open(fileName, 'w') as fileHandle:
        for line in xrange(lines):
            fileHandle.write(getRandomLine(maxLineLength))

###########################################
#Target functions
###########################################           
    
success_ratio = 0.5

def setup(target, inputFile, N):
    """Sets up the sort.
    """
    tempOutputFileStoreID = target.fileStore.getEmptyFileStoreID()
    target.addChildTargetFn(down, inputFile, 0, os.path.getsize(inputFile), N, tempOutputFileStoreID)
    target.addFollowOnTargetFn(cleanup, tempOutputFileStoreID, inputFile)

def down(target, inputFile, fileStart, fileEnd, N, outputFileStoreID):
    """Input is a file and a range into that file to sort and an output location in which
    to write the sorted file.
    If the range is larger than a threshold N the range is divided recursively and
    a follow on job is then created which merges back the results else
    the file is sorted and placed in the output.
    """
    if random.random() > success_ratio:
        raise RuntimeError() #This error is a test error, it does not mean the tests have failed.
    length = fileEnd - fileStart
    assert length >= 0
    if length > N:
        target.fileStore.logToMaster( "Splitting range (%i..%i) of file: %s"
                                      % (fileStart, fileEnd, inputFile) )
        midPoint = getMidPoint(inputFile, fileStart, fileEnd)
        assert midPoint >= fileStart
        assert midPoint+1 < fileEnd
        #We will subdivide the file
        tempFileStoreID1 = target.fileStore.getEmptyFileStoreID()
        tempFileStoreID2 = target.fileStore.getEmptyFileStoreID()
        #The use of rv here is for testing purposes
        #The rv(0) of the first child target is tempFileStoreID1, 
        #similarly rv(0) of the second child is tempFileStoreID2
        target.addFollowOnTargetFn(up, 
                                   target.addChildTargetFn(down, inputFile, fileStart, 
                                                           midPoint+1, N, tempFileStoreID1).rv(0),
                                   target.addChildTargetFn(down, inputFile, midPoint+1, 
                                                           fileEnd, N, tempFileStoreID2).rv(0), #Add one to avoid the newline
                                   outputFileStoreID)                
    else:
        #We can sort this bit of the file
        target.fileStore.logToMaster( "Sorting range (%i..%i) of file: %s"
                                      % (fileStart, fileEnd, inputFile) )
        with target.fileStore.updateGlobalFileStream(outputFileStoreID) as fileHandle:
            copySubRangeOfFile(inputFile, fileStart, fileEnd, fileHandle)
        #Make a local copy and sort the file
        tempOutputFile = target.fileStore.readGlobalFile(outputFileStoreID)
        sort(tempOutputFile)
        target.fileStore.updateGlobalFile(outputFileStoreID, tempOutputFile)
    return outputFileStoreID

def up(target, inputFileID1, inputFileID2, outputFileStoreID):
    """Merges the two files and places them in the output.
    """
    if random.random() > success_ratio:
        raise RuntimeError() #This error is a test error, it does not mean the tests have failed.
    with target.fileStore.updateGlobalFileStream(outputFileStoreID) as fileHandle:
        with target.fileStore.readGlobalFileStream( inputFileID1 ) as inputFileHandle1:
            with target.fileStore.readGlobalFileStream( inputFileID2 ) as inputFileHandle2:
                merge(inputFileHandle1, inputFileHandle2, fileHandle)
    target.fileStore.logToMaster( "Merging %s and %s to %s"
                                  % (inputFileID1, inputFileID2, outputFileStoreID) )

def cleanup(target, tempOutputFileStoreID, outputFile):
    """Copies back the temporary file to input once we've successfully sorted the temporary file.
    """
    if random.random() > success_ratio:
        raise RuntimeError() #This is a test error and not a failure of the tests
    target.fileStore.readGlobalFile(tempOutputFileStoreID, outputFile)
    #sort(outputFile)

if __name__ == '__main__':
    unittest.main()
