from abc import ABCMeta, abstractmethod
from contextlib import contextmanager
import re
import xml.etree.cElementTree as ET

class NoSuchJobException( Exception ):
    def __init__( self, jobStoreID ):
        super( NoSuchJobException, self ).__init__( "The job '%s' does not exist" % jobStoreID )

class ConcurrentFileModificationException( Exception ):
    def __init__( self, jobStoreFileID ):
        super( ConcurrentFileModificationException, self ).__init__(
            'Concurrent update to file %s detected.' % jobStoreFileID )

class NoSuchFileException( Exception ):
    def __init__( self, fileJobStoreID ):
        super( NoSuchFileException, self ).__init__( "The file '%s' does not exist" % fileJobStoreID )

class AbstractJobStore( object ):
    """ 
    Represents the physical storage for the jobs and associated files in a jobTree.
    """
    __metaclass__ = ABCMeta

    def __init__( self, config=None ):
        """
        FIXME: describe purpose and post-condition

        :param config: If config is not None then a new physical store will be created and the
        given configuration object will be written to the shared file "config.xml" which can
        later be retrieved using the readSharedFileStream. If config is None, the physical store
        is assumed to already exist and the configuration object is read the shared file
        "config.xml" in that .
        """
        if config is None:
            with self.readSharedFileStream( "config.xml" ) as fileHandle:
                self.__config = ET.parse( fileHandle ).getroot( )
        else:
            with self.writeSharedFileStream( "config.xml" ) as fileHandle:
                ET.ElementTree( config ).write( fileHandle )
            self.__config = config
        #Call cleans up any cruft in the jobStore
        self._clean()

    @property
    def config( self ):
        return self.__config
    
    @abstractmethod
    def started( self ):
        """
        Returns True if the jobStore contains existing jobs (i.e. if 
        create has already been called), else False.
        """
        raise NotImplentedError( )
    
    def loadRootJob( self ):
        """
        Returns the job created by the first call of the create method.
        """
        raise NotImplementedError( )
    
    def jobs(self):
        """
        Returns iterator on the jobs in the store.
        """
        raise NotImplentedError( )

    #
    # The following methods deal with creating/loading/updating/writing/checking for the
    # existence of jobs
    #

    @abstractmethod
    def create( self, command, memory, cpu, updateID ):
        """
        Creates a job.
        
        Command, memory, cpu and updateID are all arguments to the job.

        :rtype : job.Job
        """
        raise NotImplementedError( )

    @abstractmethod
    def exists( self, jobStoreID ):
        """
        Returns true if the job is in the store, else false.

        :rtype : bool
        """
        raise NotImplementedError( )

    @abstractmethod
    def load( self, jobStoreID ):
        """
        Loads a job for the given jobStoreID and returns it.

        :rtype : job.Job

        :raises: NoSuchJobException if there is no job with the given jobStoreID
        """
        raise NotImplementedError( )

    @abstractmethod
    def update( self, job ):
        """
        Persists the job in this store atomically.
        """
        raise NotImplementedError( )

    @abstractmethod
    def delete( self, job ):
        """
        Removes from store atomically, can not then subsequently call load(), write(), update(),
        etc. with the job.

        This operation is idempotent, i.e. deleting a job twice or deleting a non-existent job
        will succeed silently.
        """
        raise NotImplementedError( )
    
    @abstractmethod
    def loadJobsInStore(self):
        """
        Returns a list of all the jobs in the jobStore.
        """
        raise NotImplementedError( )

    ##The following provide an way of creating/reading/writing/updating files associated with a given job.

    @abstractmethod
    def writeFile( self, jobStoreID, localFilePath ):
        """
        Takes a file (as a path) and places it in this job store. Returns an ID that can be used
        to retrieve the file at a later time. jobStoreID is the id of the job from which the file
        is being created. When delete(job) is called all files written with the given
        job.jobStoreID will be removed from the jobStore.
        """
        raise NotImplementedError( )

    @abstractmethod
    def updateFile( self, jobStoreFileID, localFilePath ):
        """
        Replaces the existing version of a file in the jobStore. Throws an exception if the file
        does not exist.

        :raises ConcurrentFileModificationException: if the file was modified concurrently during
        an invocation of this method
        """
        raise NotImplementedError( )

    @abstractmethod
    def readFile( self, jobStoreFileID, localFilePath ):
        """
        Copies the file referenced by jobStoreFileID to the given local file path. The version
        will be consistent with the last copy of the file written/updated.
        """
        raise NotImplementedError( )

    @abstractmethod
    def deleteFile( self, jobStoreFileID ):
        """
        Deletes the file with the given ID from this job store. Throws an exception if the file
        does not exist.
        """
        raise NotImplementedError( )

    @abstractmethod
    @contextmanager
    def writeFileStream( self, jobStoreID ):
        """
        Similar to writeFile, but returns a context manager yielding a tuple of 1) a file handle
        which can be written to and 2) the ID of the resulting file in the job store. The yielded
        file handle does not need to and should not be closed explicitly.
        """
        raise NotImplementedError( )

    @abstractmethod
    @contextmanager
    def updateFileStream( self, jobStoreFileID ):
        """
        Similar to updateFile, but returns a context manager yielding a file handle which can be
        written to. The yielded file handle does not need to and should not be closed explicitly.

        :raises ConcurrentFileModificationException: if the file was modified concurrently during
        an invocation of this method
        """
        raise NotImplementedError( )

    @abstractmethod
    def getEmptyFileStoreID( self, jobStoreID ):
        """
        Returns the ID of a new, empty file.
        """
        raise NotImplementedError( )

    @abstractmethod
    @contextmanager
    def readFileStream( self, jobStoreFileID ):
        """
        Similar to readFile, but returns a context manager yielding a file handle which can be
        read from. The yielded file handle does not need to and should not be closed explicitly.
        """
        raise NotImplementedError( )

    #
    # The following methods deal with shared files, i.e. files not associated with specific jobs.
    #

    sharedFileNameRegex = re.compile( r'^[a-zA-Z0-9._-]+$' )

    # FIXME: Rename to updateSharedFileStream

    @abstractmethod
    @contextmanager
    def writeSharedFileStream( self, sharedFileName ):
        """
        Returns a context manager yielding a writable file handle to the global file referenced
        by the given name.

        :param sharedFileName: A file name matching AbstractJobStore.fileNameRegex, unique within
        the physical storage represented by this job store

        :raises ConcurrentFileModificationException: if the file was modified concurrently during
        an invocation of this method
        """
        raise NotImplementedError( )

    @abstractmethod
    @contextmanager
    def readSharedFileStream( self, sharedFileName ):
        """
        Returns a context manager yielding a readable file handle to the global file referenced
        by the given ID.
        """
        raise NotImplementedError( )

    @abstractmethod
    def writeStatsAndLogging( self, statsAndLoggingString ):
        """
        Adds the given statistics/logging string to the store of statistics info.
        """
        raise NotImplementedError( )

    @abstractmethod
    def readStatsAndLogging( self, statsAndLoggingCallBackFn):
        """
        Reads stats/logging strings accumulated by "writeStatsAndLogging" function. 
        For each stats/logging file calls the statsAndLoggingCallBackFn with 
        an open, readable file-handle that can be used to parse the stats.
        Returns the number of stat/logging strings processed. 
        Stats/logging files are only read once and are removed from the 
        file store after being written to the given file handle.
        """
        raise NotImplementedError( )
    
    @abstractmethod
    def deleteJobStore( self ):
        """
        Removes the jobStore from the disk/store. Careful!
        """
        raise NotImplementedError( )

    ## Helper methods for subclasses

    def _defaultTryCount( self ):
        return int( self.config.attrib[ "try_count" ] )

    @classmethod
    def _validateSharedFileName( cls, sharedFileName ):
        return bool( cls.sharedFileNameRegex.match( sharedFileName ) )
    
    ##Cleanup functions
    
    def _clean(self):
        """
        Function to cleanup the state of a jobStore after a restart.
        Fixes jobs that might have been partially updated. Is called by constructor.
        """
        if self.started():
            #Collate any jobs that were in the process of being created/deleted
            jobsToDelete = set()
            for job in self.jobs():
                 for updateID in job.jobsToDelete:
                     jobsToDelete.add(updateID)
                
            #Delete the jobs that should be delete
            if len(jobsToDelete) > 0:
                for job in self.jobs():
                    if job.updateID in jobsToDelete:
                        self.delete(job.jobStoreID)
            
            #Cleanup the state of each job
            for job in self.jobs():
                changed = False #Flag to indicate if we need to update the job
                #on disk
                
                if len(job.jobsToDelete) != 0:
                    job.jobsToDelete = set()
                    changed = True
                    
                #While jobs at the end of the stack are already deleted remove
                #those jobs from the stack (this cleans up the case that the job
                #had successors to run, but had not been updated to reflect this)
                while len(job.stack) > 0:
                    jobs = [ jobStoreID for jobStoreID in job.stack[-1] if self.exists(jobStoreID) ]
                    if len(jobs) > 0:
                        if len(jobs) < len(job.stack[-1]):
                            job.stack[-1] = jobs
                            changed = True
                        break
                    job.stack.pop()
                              
                #This cleans the old log file which may 
                #have been left if the job is being retried after a job failure. 
                if job.logJobStoreFileID != None:
                    job.clearLogFile(self) 
                    changed = True
                
                if changed: #Update, but only if a change has occurred
                    self.update(job)
