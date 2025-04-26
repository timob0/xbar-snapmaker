#!/usr/bin/env PYTHONIOENCODING=UTF-8 PYTHONWARNINGS=ignore python3
# Requires: sudo pip3 install requests
#
import socket
import requests
import json
import urllib3
import ipaddress
import time
from datetime import timedelta
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

bufferSize = 1024
msg = b'discover'
destPort = 20054
sockTimeout = 1.0
retries = 5
retryCounter = 0
snReply = {}
connectIP = ''
tokenfile = '/Users/timo/SMtoken.txt' # Set to writable path, file will be created if not exists.
snWorking = ''
debuglog = '/Users/timo/snaplog.txt'

# Main Program
def main():
    global connectIP
    UDPClientSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
    UDPClientSocket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    UDPClientSocket.settimeout(sockTimeout)
    
    # Get Status and IP of Snapmaker
    checkState(UDPClientSocket,msg,destPort,retries)
    if validate_ip_address(snReply.get("snIP")):
        connectIP = snReply.get("snIP")
        SMtoken = getSMToken(connectIP)
        postIt(readStatus(SMtoken), readStatusEnclosure(SMtoken))
    else:
        postIt(snReply, None)

def getSMToken(connectIP):
    # Create file if not exists
    try:
        f = open(tokenfile, "r+")
    except FileNotFoundError:
        f = open(tokenfile, "w+")
        
    SMurl = "http://" + connectIP + ":8080/api/v1/connect"
    SMtoken = f.read()
    if SMtoken == "":
        # Create token
        connected = False
        while not connected:
            # print("Please confirm connection on touchscreen in 15s.")
            time.sleep(15)
            r = requests.post(SMurl)
            # time.sleep(10)
            if "Failed" in r.text:
                print(r.text)
                # print("Binding failed, please try again.")
                exit(1)
            
            # Grab token from response and save it
            SMtoken = (json.loads(r.text).get("token"))
            headers = {'Content-Type' : 'application/x-www-form-urlencoded'}
            formData = {'token' : SMtoken}
            r = requests.post(SMurl, data=formData, headers=headers)
            if json.loads(r.text).get("token") == SMtoken:
                f.write(SMtoken)
                f.close()
                # print("Token received and saved.")
                connected = True
                return(SMtoken)

    # We have a pre-saved token
    else:
        f.close()
        # Connect to SnapMaker with saved token
        headers = {'Content-Type' : 'application/x-www-form-urlencoded'}
        formData = {'token' : SMtoken}
        r = requests.post(SMurl, data=formData, headers=headers)
        return(SMtoken)


# Get Status of Snapmaker 2.0 via API
def readStatus(SMtoken):
    
    with open(debuglog, "a") as f:
        f.write("readStatus")
        SMstatus = "http://" + connectIP + ":8080/api/v1/status?token="
        r = requests.get(SMstatus+SMtoken)
        f.write(r.text)
        snStatus = json.loads(r.text).get("status")
        snNozzleTemp = json.loads(r.text).get("nozzleTemperature")
        snNozzleTaTemp = json.loads(r.text).get("nozzleTargetTemperature")
        snHeatedBedTemp = json.loads(r.text).get("heatedBedTemperature")
        snHeatedBedTaTemp = json.loads(r.text).get("heatedBedTargetTemperature")
    
        if json.loads(r.text).get("fileName") is not None:
            snFileName = json.loads(r.text).get("fileName") 
        else:
            snFileName = "N/A"
        if json.loads(r.text).get("progress") is not None:
            snProgress = ("{:0.1f}".format(json.loads(r.text).get("progress")*100))
        else:
            snProgress = "0"
        if json.loads(r.text).get("elapsedTime") is not None:
            snElapsedTime = str(timedelta(seconds=json.loads(r.text).get("elapsedTime")))
        else:
            snElapsedTime = "00:00:00"
        if json.loads(r.text).get("remainingTime") is not None:
            snRemainingTime = str(timedelta(seconds=json.loads(r.text).get("remainingTime")))
        else:
            snRemainingTime = "00:00:00"
    
        if json.loads(r.text).get("isEnclosureDoorOpen") is not None:
            snEncDoorOpen = json.loads(r.text).get("isEnclosureDoorOpen") 
        else:
            snEncDoorOpen = "N/A"

        if json.loads(r.text).get("isFilamentOut") is not None:
            snFilamentOut = json.loads(r.text).get("isFilamentOut") 
        else:
            snFilamentOut = "N/A"       
            
        snReply = {"snIP":connectIP,"snStatus":snStatus,"snNozzleTemp":snNozzleTemp,"snNozzleTaTemp":snNozzleTaTemp,
               "snHeatedBedTemp":snHeatedBedTemp,"snHeatedBedTaTemp":snHeatedBedTaTemp,"snFileName":snFileName,
               "snProgress":snProgress,"snElapsedTime":snElapsedTime,"snRemainingTime":snRemainingTime,
               "snEncDoorOpen":snEncDoorOpen, "snFilamentOut":snFilamentOut}
        return(snReply)
  
# Read Status of Enclosure
# Example Data:
# {"isReady":true,"isDoorEnabled":false,"led":100,"fan":0}
#  
def readStatusEnclosure(SMtoken):
    with open(debuglog, "a") as f:
        f.write("readEnclosure")
        # SMstatus = "http://" + connectIP + ":8080/api/v1/status?token="
        # r = requests.get(SMstatus+SMtoken)
        SMenclosure = "http://" + connectIP + ":8080/api/v1/enclosure?token="
        r = requests.get(SMenclosure+SMtoken)
        f.write(r.text)
        # Response format {"isReady":true,"isDoorEnabled":false,"led":100,"fan":0}
        if json.loads(r.text).get("isReady") is not None:
            snEncReady = json.loads(r.text).get("isReady") 
        else:
            snEncReady = "N/A"    

        if json.loads(r.text).get("isEnclosureDoorOpen") is not None:
            snEncDoor = json.loads(r.text).get("isEnclosureDoorOpen") 
        else:
            snEncDoor = "N/A"

        if json.loads(r.text).get("isFilamentOut") is not None:
            snEncDoor = json.loads(r.text).get("isFilamentOut") 
        else:
            snEncDoor = "N/A"         

        if json.loads(r.text).get("led") is not None:
            snEncLed = f"{json.loads(r.text).get('led')}"
        else:
            snEncLed = "N/A"    
            
        if json.loads(r.text).get("fan") is not None:
            snEncFan = f"{json.loads(r.text).get('fan')}"
        else:
            snEncFan = "N/A"

        snReply = {"snEncReady":snEncReady,"snEncDoor":snEncDoor,"snEncLed":snEncLed,"snEncFan":snEncFan}
        return(snReply)


# Check status of Snapmaker 2.0 via UDP Discovery
# Possible replies:
#  'Snapmaker@X.X.X.X|model:Snapmaker 2 Model A350|status:IDLE'
#  'Snapmaker@X.X.X.X|model:Snapmaker 2 Model A350|status:RUNNING'
def checkState(UDPClientSocket,msg,destPort,retries):
    global snReply
    global snWorking
    global retryCounter
    UDPClientSocket.sendto(msg, ("255.255.255.255", destPort))
    try:
        reply, server_address_info = UDPClientSocket.recvfrom(1024)
        elements = str(reply).split('|')
        snIP = (elements[0]).replace('\'','')
        snModel = (elements[1]).replace('\'','')
        snStatus = (elements[2]).replace('\'','')
        snIP, snIPVal = snIP.split('@')
        snModel, snModelVal = snModel.split(':')
        snStatus, snStatusVal = snStatus.split(':')
        snWorking = snStatusVal
        snReply = {"snIP":snIPVal, "model":snModelVal, "snStatus":snStatusVal}
    except socket.timeout:
        retryCounter += 1
        if (retryCounter==retries): 
          snReply = {"snIP":"N/A", "model":"N/A", "snStatus":"OFFLINE",
                     "snNozzleTemp":0,"snNozzleTaTemp":0,
                     "snHeatedBedTemp":0,"snHeatedBedTaTemp":0,"snFileName":"N/A",
                     "snProgress":0,"snElapsedTime":"00:00:00","snRemainingTime":"00:00:00"}
          return
        else:
          checkState(UDPClientSocket,msg,destPort,retries);
          
# Check if IP is valid:          
def validate_ip_address(ip_string):
   try:
       ip_object = ipaddress.ip_address(ip_string)
       return True
   except ValueError:
       return False

def xbarMetadata():
    print("# Display Snapmaker v2 Status.")
    print("#")
    print("# by Timo Biesenbach (biesenhome.de)")
    print("#")
    print("# metadata")
    print("# <xbar.title>Snapmaker Status</xbar.title>")
    print("# <xbar.version>v1.0.0</xbar.version>")
    print("# <xbar.author>Timo Biesenbach</xbar.author>")
    print("# <xbar.author.github>timob0</xbar.author.github>")
    print("# <xbar.desc>Display Snapmaker v2 Status.</xbar.desc>")
    print("# <xbar.image></xbar.image>")

# Update XBar
def postIt(state, encState):
    scale      = "─┬─┬─┬─┬─┼─┬─┬─┬─┬─"
    scaleStart = "├"
    scaleEnd   = "┤"
    bar        = "▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓"
    
    bargraph   = "▁▂▃▄▅▆▇█"
    
    print(f"Snapmaker")
    print(f"---")
    print(f"Address   {state['snIP']} | font=JetBrainsMono-Regular bash=null")
    print(f"Status    {state['snStatus']} | font=JetBrainsMono-Regular bash=null")
    if (state is not None and state['snStatus']!="IDLE" and state['snStatus']!="OFFLINE"):
        numBlocks = int(float(state['snProgress'])/5) # 10)*2
        # Cut one to leave the begin of scale
        scBlocks = 0
        brBlocks = 0
        
        if (numBlocks>0):
            brBlocks=numBlocks
            scBlocks=numBlocks
        
        if (numBlocks>=20):
            brBlocks=numBlocks-1
            scBlocks=len(scale)-1
        
        progressMeter = f"{scaleStart}{bar[:brBlocks]}{scale[scBlocks:]}{scaleEnd}"
        print(f"Printing  {state['snFileName']} | font=JetBrainsMono-Regular bash=null")
        print(f"Progress  {progressMeter} {state['snProgress']}% | font=JetBrainsMono-Regular bash=null")
        print(f"Elapsed   {state['snElapsedTime']} | font=JetBrainsMono-Regular bash=null")
        print(f"Remaining {state['snRemainingTime']} | font=JetBrainsMono-Regular bash=null")
        print(f"---")
        print(f"Temperatures")
        
        nozzleBars = int(float(state['snNozzleTemp']) / float(state['snNozzleTaTemp']) * 8)
        bgraphNozzle = f"{bargraph[:nozzleBars]}"
        
        bedBars = int(float(state['snHeatedBedTemp']) / float(state['snHeatedBedTaTemp']) * 8)
        bgraphBed = f"{bargraph[:bedBars]}"
        
        print(f"⍒  Nozzle    {state['snNozzleTemp']}°C  {bgraphNozzle}  [{state['snNozzleTaTemp']}°C] | font=JetBrainsMono-Regular bash=null")
        print(f"≋  Heatbed   {state['snHeatedBedTemp']}°C  {bgraphBed}  [ {state['snHeatedBedTaTemp']}°C] | font=JetBrainsMono-Regular bash=null")
        print(f"~> Filament  {'⚠ Out or broken' if state['snFilamentOut'] else '✓ Okay'} | font=JetBrainsMono-Regular bash=null")
        
    if (encState is not None and encState['snEncReady']==True):
        print(f"---")
        print(f"Enclosure")

        print(f"◫ Door     {'⚠ Open' if state['snEncDoorOpen'] else '■ Closed'} | font=JetBrainsMono-Regular bash=null")       	
        
        ledBars = int(float(encState['snEncLed']) / 100.0 * 8)
        bgraphLed = f"{bargraph[:ledBars]}"
        
        fanBars = int(float(encState['snEncFan']) / 100.0 * 8)
        bgraphFan = f"{bargraph[:fanBars]}"
       
        print(f"◌ Lights   {encState['snEncLed']}%   {bgraphLed} | font=JetBrainsMono-Regular bash=null")
        print(f"✗ Fan      {encState['snEncFan']}%   {bgraphFan} | font=JetBrainsMono-Regular bash=null")

    print(f"---")        
    print(f"Tools")
    print(f"Launch Cura... | font=JetBrainsMono-Regular bash='/Applications/UltiMaker Cura.app/Contents/MacOS/UltiMaker-Cura' terminal=false")  
    print(f"Launch Fusion... | font=JetBrainsMono-Regular bash='/Users/timo/Applications/Autodesk Fusion.app/Contents/MacOS/Autodesk Fusion' terminal=false")        

# Run Main Program
main()
