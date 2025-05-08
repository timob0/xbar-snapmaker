#!/usr/bin/env PYTHONIOENCODING=UTF-8 PYTHONWARNINGS=ignore python3
# Requires: sudo pip3 install requests
#
#  <xbar.title>Snapmaker 2 status</xbar.title>
#  <xbar.version>v1.0.0</xbar.version>
#  <xbar.author>Timo Biesenbach</xbar.author>
#  <xbar.author.github>timob0</xbar.author.github>
#  <xbar.desc>Display Snapmaker v2 status.</xbar.desc>
#  <xbar.image>https://github.com/timob0/xbar-snapmaker/blob/main/snapStatus.png</xbar.image>
#  <xbar.var>boolean(VAR_LOGGING=true): If true, logs Snapmaker status data to snaplog.txt.</xbar.var>
#  <xbar.var>string(VAR_TOOL1NAME="Cura"): Tool 1 to show in the Launch... menu.</xbar.var>
#  <xbar.var>string(VAR_TOOL1PATH="/Applications/UltiMaker Cura.app/Contents/MacOS/UltiMaker-Cura"): Path to tool 1.</xbar.var>
#  <xbar.var>string(VAR_TOOL2NAME="Fusion"): Tool 2 to show in the Launch... menu.</xbar.var>
#  <xbar.var>string(VAR_TOOL2PATH="/Users/timo/Applications/Autodesk Fusion.app/Contents/MacOS/Autodesk Fusion"): Path to tool 2.</xbar.var>
#  <xbar.var>string(VAR_TOOL3NAME=""): Tool 3 to show in the Launch... menu.</xbar.var>
#  <xbar.var>string(VAR_TOOL3PATH=""): Path to tool 3.</xbar.var>
#  <xbar.var>string(VAR_TOOL4NAME=""): Tool 4 to show in the Launch... menu.</xbar.var>
#  <xbar.var>string(VAR_TOOL4PATH=""): Path to tool 4.</xbar.var>

import socket
import requests
import json
import urllib3
import ipaddress
import time
import os
import sys
from datetime import timedelta
from pathlib import Path
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

bufferSize = 1024
msg = b'discover'
destPort = 20054
sockTimeout = 1.0
retries = 5
retryCounter = 0
snReply = {}
connectIP = ''

configpath = os.environ.get('HOME')     # Store config in user home folder
tokenfile  = f"{configpath}/.snaptoken.txt"
snWorking  = ''
dolog      = True if os.environ.get('VAR_LOGGING')=="true" else False
debuglog   = f"{configpath}/snap.log"
scriptname = str(Path( __file__ ).absolute())

# Main Program
def main(args):
	global connectIP
	UDPClientSocket = socket.socket(family=socket.AF_INET, type=socket.SOCK_DGRAM)
	UDPClientSocket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
	UDPClientSocket.settimeout(sockTimeout)
	
	# Get Status and IP of Snapmaker
	checkState(UDPClientSocket,msg,destPort,retries)
	if validate_ip_address(snReply.get("snIP")):
		connectIP = snReply.get("snIP")
	
		# Check if reconnection request        
		if (len(args)==1 and args[0]=='-reconnect'):
			log("Reconnect to snapmaker requested.", args[0])
			reconnect()
			exit(0)
		
		SMtoken = getSMToken(connectIP)
		postIt(readStatus(SMtoken), readStatusEnclosure(SMtoken), snReply)
	else:
		postIt(None, None, snReply)

# Delete token and re-authorize.
def reconnect():
	if os.path.exists(tokenfile):
		os.remove(tokenfile)
	
	f = open(tokenfile, "w+")
	SMurl = "http://" + connectIP + ":8080/api/v1/connect"
	SMtoken = authorize(SMurl, f)
    

# authorize this script with the Snapmaker machine via the touchscreen.
def authorize(SMurl, file):
	timer=15
	while timer>0:
		clear_screen()
		print(f"╔═════════════════════════════════════════════════════════════════════════╗")
		print(f"║ Connecting to Snapmaker 2                                               ║")
		print(f"╟─────────────────────────────────────────────────────────────────────────╢")		
		print(f"║ Confirm connection request on machine's touchscreen in {timer:02}s...           ║")		
		print(f"╚═════════════════════════════════════════════════════════════════════════╝")
		time.sleep(1)
		timer=timer-1
	
	r = requests.post(SMurl)
	log("authorize",r.text)
	if "Failed" in r.text:
		print(f"╔═════════════════════════════════════════════════════════════════════════╗")
		print(f"║ ⚠  Failed to connect to Snapmaker. Please try again.                    ║")
		print(f"╟─────────────────────────────────────────────────────────────────────────╢")
		print(f"║ ▶  You can now close this terminal window.                              ║")		
		print(f"╚═════════════════════════════════════════════════════════════════════════╝")		
		exit(1)

	# Grab token from response and save it
	SMtoken = (json.loads(r.text).get("token"))
	headers = {'Content-Type' : 'application/x-www-form-urlencoded'}
	formData = {'token' : SMtoken}
	r = requests.post(SMurl, data=formData, headers=headers)
	if json.loads(r.text).get("token") == SMtoken:
		file.write(SMtoken)
		file.close()
		print(f"╔═════════════════════════════════════════════════════════════════════════╗")
		print(f"║ ✓  Successfully connected.                                              ║")
		print(f"║ ✓  Token saved to .snaptoken.txt                                        ║")
		print(f"╟─────────────────────────────────────────────────────────────────────────╢")
		print(f"║ ▶  You can now close this terminal window.                              ║")		
		print(f"╚═════════════════════════════════════════════════════════════════════════╝")			
		connected = True
		return(SMtoken)

def getSMToken(connectIP):
	SMurl = "http://" + connectIP + ":8080/api/v1/connect"
	# Read token from file.
	try:
		f = open(tokenfile, "r+")
		SMtoken = f.read()
		f.close()

		headers = {'Content-Type' : 'application/x-www-form-urlencoded'}
		formData = {'token' : SMtoken}
		r = requests.post(SMurl, data=formData, headers=headers)
		return(SMtoken)
	
	except FileNotFoundError:
		f = open(tokenfile, "w+")
		return ""

def log(component, message):
	if dolog:
		with open(debuglog, "a") as f:
			f.write(component +": "+ message + "\n")

# Get Status of Snapmaker 2.0 via API
def readStatus(token):
	statusrequest = f"http://{connectIP}:8080/api/v1/status?token={token}"
	r = requests.get(statusrequest)
	
	log("readStatus", r.text)
	
	if r.text=="Machine is not connected yet.":
		return({"snIP":connectIP,"snStatus":"NOT_CONNECTED"})
	
	status = json.loads(r.text)
	snStatus = status["status"]
	snNozzleTemp      = status["nozzleTemperature"]
	snNozzleTaTemp    = status["nozzleTargetTemperature"]
	snHeatedBedTemp   = status["heatedBedTemperature"]
	snHeatedBedTaTemp = status["heatedBedTargetTemperature"]
	
	
	snFileName      = status.get("fileName","N/A")  
	snProgress      = ("{:0.1f}".format(status.get("progress",0)*100))
	snElapsedTime   = str(timedelta(seconds=status.get("elapsedTime",0)))
	snRemainingTime = str(timedelta(seconds=status.get("remainingTime",0)))
	snEncDoorOpen   = status.get("isEnclosureDoorOpen","N/A") 
	snFilamentOut   = status.get("isFilamentOut","N/A") 
	
	# TOOLHEAD_3DPRINTING_1
	snToolHead = status.get("toolHead","N/A")
	
	# Check installed options
	if "moduleList" in status.keys():
		snOptionEnc  = status["moduleList"]["enclosure"]
		snOptionRot  = status["moduleList"]["rotaryModule"]
		snOptionStop = status["moduleList"]["emergencyStopButton"]
		snOptionAir  = status["moduleList"]["airPurifier"]
	
	snReply = {"snIP":connectIP,"snStatus":snStatus,"snNozzleTemp":snNozzleTemp,"snNozzleTaTemp":snNozzleTaTemp,
		   "snHeatedBedTemp":snHeatedBedTemp,"snHeatedBedTaTemp":snHeatedBedTaTemp,"snFileName":snFileName,
		   "snProgress":snProgress,"snElapsedTime":snElapsedTime,"snRemainingTime":snRemainingTime,
		   "snEncDoorOpen":snEncDoorOpen, "snFilamentOut":snFilamentOut, "snToolHead":snToolHead,
		   "snOptionEnc":snOptionEnc, "snOptionRot":snOptionRot, "snOptionStop":snOptionStop, "snOptionAir":snOptionAir}
	return(snReply)
  
# Read Status of Enclosure
# Example Data:
# {"isReady":true,"isDoorEnabled":false,"led":100,"fan":0}
#  
def readStatusEnclosure(SMtoken):
	SMenclosure = "http://" + connectIP + ":8080/api/v1/enclosure?token="
	r = requests.get(SMenclosure+SMtoken)
	
	log("readStatusEnclosure", r.text)

	if r.text=="Machine is not connected yet.":
		return None

	# Response format {"isReady":true,"isDoorEnabled":false,"led":100,"fan":0}
	status = json.loads(r.text)
	if status.get("isReady") is not None:
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

# Update XBar
def postIt(state, encState, bcReply):
	scale      = "─┬─┬─┬─┬─┼─┬─┬─┬─┬─"
	scaleStart = "├"
	scaleEnd   = "┤"
	bar        = "▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓"
	
	bargraph   = "▁▂▃▄▅▆▇█"
	
	print(f"Snapmaker - {bcReply['snStatus']}")
	print(f"---")
	print(f"Model     {bcReply['model']} | font=JetBrainsMono-Regular bash=null")
	print(f"Address   {bcReply['snIP']} | font=JetBrainsMono-Regular bash=null")
	# print(f"Conf.path {os.environ.get('HOME')} | font=JetBrainsMono-Regular bash=null")
	
	if (state is not None and state['snStatus']=="NOT_CONNECTED"):
		print(f"⚠ Reconnect to Snapmaker in setup menu.  | font=JetBrainsMono-Regular bash=null color=purple")
	
	if (state is not None and state['snStatus']!="NOT_CONNECTED"):
		print(f"---\nInstalled options")
		print(f"Enclosure      {'✓' if state['snOptionEnc']  else '✕'}  | font=JetBrainsMono-Regular bash=null")
		print(f"Rotary Module  {'✓' if state['snOptionRot']  else '✕'}  | font=JetBrainsMono-Regular bash=null")
		print(f"Stop Button    {'✓' if state['snOptionStop'] else '✕'}  | font=JetBrainsMono-Regular bash=null")
		print(f"Air Purifier   {'✓' if state['snOptionAir']  else '✕'}  | font=JetBrainsMono-Regular bash=null")
	
		print(f"---\nMachine")
		print(f"Status    {state['snStatus']} | font=JetBrainsMono-Regular bash=null")
	
	if (state is not None and state['snStatus']!="IDLE" and state['snStatus']!="OFFLINE" and state['snStatus']!="NOT_CONNECTED"):
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
		print(f"File      {state['snFileName']} | font=JetBrainsMono-Regular bash=null")
		print(f"Progress  {progressMeter} {state['snProgress']}% | font=JetBrainsMono-Regular bash=null")
		print(f"Elapsed   {state['snElapsedTime']} | font=JetBrainsMono-Regular bash=null")
		print(f"Remaining {state['snRemainingTime']} | font=JetBrainsMono-Regular bash=null")
			
		print(f"---")
		print(f"3D Printing")
		
		print(f"Toolhead     {'Single Extrusion' if state['snToolHead']=='TOOLHEAD_3DPRINTING_1' else 'unknown'} | font=JetBrainsMono-Regular bash=null")
		
		nozzleBars = int(float(state['snNozzleTemp']) / float(state['snNozzleTaTemp']) * 8)
		bgraphNozzle = f"{bargraph[:nozzleBars]}"
		
		bedBars = int(float(state['snHeatedBedTemp']) / float(state['snHeatedBedTaTemp']) * 8)
		bgraphBed = f"{bargraph[:bedBars]}"
		
		print(f"⍒  Nozzle    {state['snNozzleTemp']}°C  {bgraphNozzle}  [{state['snNozzleTaTemp']}°C] | font=JetBrainsMono-Regular bash=null")
		print(f"≋  Heatbed   {state['snHeatedBedTemp']}°C  {bgraphBed}  [ {state['snHeatedBedTaTemp']}°C] | font=JetBrainsMono-Regular bash=null")
		print(f"~> Filament  {'⚠ Out or broken' if state['snFilamentOut'] else '✓ Okay'} | font=JetBrainsMono-Regular bash=null")
		
	if (encState is not None and encState['snEncReady']==True and state['snStatus']!="NOT_CONNECTED"):
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
	if (os.environ.get('VAR_TOOL1NAME')!=None and os.environ.get('VAR_TOOL1NAME')!=""):
		tool_name = os.environ.get('VAR_TOOL1NAME')
		tool_path = os.environ.get('VAR_TOOL1PATH')
		print(f"Launch {tool_name}... | font=JetBrainsMono-Regular bash='{tool_path}' terminal=false")  
	
	if (os.environ.get('VAR_TOOL2NAME')!=None and os.environ.get('VAR_TOOL2NAME')!=""):
		tool_name = os.environ.get('VAR_TOOL2NAME')
		tool_path = os.environ.get('VAR_TOOL2PATH')
		print(f"Launch {tool_name}... | font=JetBrainsMono-Regular bash='{tool_path}' terminal=false")  
		
	if (os.environ.get('VAR_TOOL3NAME')!=None and os.environ.get('VAR_TOOL3NAME')!=""):
		tool_name = os.environ.get('VAR_TOOL3NAME')
		tool_path = os.environ.get('VAR_TOOL3PATH')
		print(f"Launch {tool_name}... | font=JetBrainsMono-Regular bash='{tool_path}' terminal=false")  
			
	if (os.environ.get('VAR_TOOL4NAME')!=None and os.environ.get('VAR_TOOL4NAME')!=""):
		tool_name = os.environ.get('VAR_TOOL4NAME')
		tool_path = os.environ.get('VAR_TOOL4PATH')
		print(f"Launch {tool_name}... | font=JetBrainsMono-Regular bash='{tool_path}' terminal=false")  
	
	print(f"---")        
	print(f"Setup")    
	print(f"Reconnect... | font=JetBrainsMono-Regular shell='{scriptname}' param1=-reconnect terminal=true refresh=true")

# functions for reconnecting
def clear_screen():
	print('\033c', end='')

# Main entry point
if __name__ == "__main__":
	args = sys.argv[1:]
	log("main", scriptname)
	
	main(args)
