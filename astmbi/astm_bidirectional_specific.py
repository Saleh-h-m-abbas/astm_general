#!/usr/bin/python3
import astm_bidirectional_general as astmg
import astm_bidirectional_conf as conf

from astm_bidirectional_common import my_sql
from astm_bidirectional_common import file_mgmt

class astms(astmg.astmg, file_mgmt):
  def __init__(self):
    self.main_status=0
          #0=neutral
          #1=receiving
          #2=sending

    self.send_status=0
          #1=enq sent
          #2=1st ack received
          #3=data sent
          #4=2nd ack received
          #0=eot sent

    self.set_inbox(conf.inbox_data,conf.inbox_arch)
    self.set_outbox(conf.outbox_data,conf.outbox_arch)

    super().__init__()

  ###################################
  #override this function in subclass
  ###################################
  def manage_read(self,data):

    #for receiving data
    if(data==b'\x05'):
      self.main_status=1
      self.write_msg=b'\x06'
      self.write_set.add(self.conn[0])                      #Add in write set, for next select() to make it writable
      self.error_set=self.read_set.union(self.write_set)    #update error set
    if(data==b'\x0a'):
      self.write_msg=b'\x06'
      self.write_set.add(self.conn[0])                      #Add in write set, for next select() to make it writable
      self.error_set=self.read_set.union(self.write_set)    #update error set      
      
    if(data==b'\x04'):
      self.main_status=0
      self.send_status=0
      #no need update set write_set
      
    #for sending data
    if(data==b'\x06'):                  #ACK
      if(self.send_status==1):
        self.send_status=2
        self.print_to_log('send_status=={}'.format(self.send_status),'post-ENQ ACK')

      if(self.send_status==3):
        self.send_status=4
        self.print_to_log('send_status=={}'.format(self.send_status),'post-LF ACK')

    if(data==b'\x15'):            #NAK
      self.send_status=4
      self.print_to_log('send_status=={}'.format(self.send_status),'post-LF NAK. Some error')
        
  ###################################
  #override this function in subclass
  ###################################
  def initiate_write(self):
    self.print_to_log('main_status={} send_status={}'.format(self.main_status,self.send_status),' Entering initiate_write()') 
    if(self.main_status!=0):
      self.print_to_log('main_status={} send_status={}'.format(self.main_status,self.send_status),'busy somewhre.. initiate_write() will not initiate anything') 
    else:
      self.print_to_log('main_status=={}'.format(self.main_status),'initiate_write() will find some pending work') 
      if(self.get_first_outbox_file()==True):                 #There is something to work      
        self.main_status=2                                    #announce that we are busy sending data
        self.print_to_log('main_status=={}'.format(self.main_status),'initiate_write() changed main_status to 2 to send data')
      else:
        self.print_to_log('main_status=={}'.format(self.main_status),'no data in outbox. sleeping for a while')
        return

    if(self.main_status==2):                                #in process of sending
      if(self.send_status==0):                                #eot was sent for sending
        self.write_set.add(self.conn[0])                      #Add in write set, for next select() to make it writable
        self.error_set=self.read_set.union(self.write_set)    #update error set
        self.write_msg=b'\x05'                                #set message ENQ
        self.send_status=1                                    #status to ENQ sent
        self.print_to_log('send_status=={}'.format(self.send_status),'initiate_write() sent ENQ to write buffer')
        
      elif(self.send_status==2):                              #First ACK received. Time to send data 
        self.write_set.add(self.conn[0])                      #Add in write set, for next select() to make it writable
        self.error_set=self.read_set.union(self.write_set)    #update error set
        
        self.get_first_outbox_file()                          #set current_outbox file
        fd=open(self.current_outbox_file,'rb')
        byte_data=fd.read(1024)
        self.print_to_log('File Content',byte_data)
        chksum=self.get_checksum(byte_data)
        self.print_to_log('CHKSUM',chksum)
        self.write_msg=byte_data #set message
        self.send_status=3                                    #dat sent
        self.print_to_log('send_status=={}'.format(self.send_status),'initiate_write() changed send_status to 3 (data sent to write buffer)')

      elif(self.send_status==4):                              #Second ACK received. Time to send data 
        self.write_set.add(self.conn[0])                      #Add in write set, for next select() to make it writable
        self.error_set=self.read_set.union(self.write_set)    #update error set
        self.write_msg=b'\x04'                                #set message EOT
        self.archive_outbox_file()
        self.send_status=0                                    #dat sent
        self.main_status=0
        self.print_to_log('send_status=={}'.format(self.send_status),'initiate_write() sent EOT')
        self.print_to_log('main_status=={}'.format(self.main_status),'initiate_write() now, neutral')
        
  def get_checksum(self,data):
    checksum=0
    start_chk_counting=False
    for x in data:
      if(x==2):
        start_chk_counting=True
        continue

      if(start_chk_counting==True):
        checksum=(checksum+x)%256

      if(x==3):
        start_chk_counting=False
        #continue
      if(x==23):
        start_chk_counting=False
        #continue
 
    two_digit_checksum_string='{:X}'.format(checksum).zfill(2)
    return two_digit_checksum_string


#Main Code###############################
#use this to device your own script
if __name__=='__main__':
  #print('__name__ is ',__name__,',so running code')
  while True:
    m=astms()
    m.astmg_loop()
    #break; #useful during debugging  
    
