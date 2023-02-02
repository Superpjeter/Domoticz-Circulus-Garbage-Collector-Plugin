########################################################################################
# 	Circulus Garbage calendar Plugin for Domoticz                                   	   #
#                                                                                      #
# 	MIT License                                                                        #
#                                                                                      #
#	Copyright (c) 2023                                                           #
#                                                                                      #
#	Permission is hereby granted, free of charge, to any person obtaining a copy       #
#	of this software and associated documentation files (the "Software"), to deal      #
#	in the Software without restriction, including without limitation the rights       #
#	to use, copy, modify, merge, publish, distribute, sublicense, and/or sell          #
#	copies of the Software, and to permit persons to whom the Software is              #
#	furnished to do so, subject to the following conditions:                           #
#                                                                                      #
#	The above copyright notice and this permission notice shall be included in all     #
#	copies or substantial portions of the Software.                                    #
#                                                                                      #
#	THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR         #
#	IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,           #
#	FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE        #
#	AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER             #
#	LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,      #
#	OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE      #
#	SOFTWARE.                                                                          #
#                                                                                      #
#   Author: pvdm                                                                     #
#                                                                                      #
#   This plugin will read the garbadge dates from Circulus via the webservice.     #
#                                                                                      #
#   V 1.0.0. Initial Release (12-01-2023)                                              #
########################################################################################


"""
<plugin key="CirculusGarbageCollector" name="Circulus Garbage Collector" author="PvdM" version="0.0.0" externallink="https://mijn.circulus.nl">
    <description>
        <h2>Circulus Garbage Collector </h2><br/>
<!--
        Will hit the supplied URL every 5 heartbeats in the request protocol.  Redirects are handled.
-->
    </description>
    <params>
        <param field="Mode1" label="Postal Code" width="100px" required="true" default="0000AA"/>
        <param field="Mode2" label="House Number" width="100px" required="true" default="1"/>
        <param field="Address" label="IP Address" width="400px" required="true" default="mijn.circulus.nl"/>
<!--        <param field="Mode1" label="Protocol" width="75px">
            <options>
                <option label="HTTPS" value="443"/>
                <option label="HTTP" value="80"  default="true" />
            </options>
        </param>
-->
        <param field="Mode6" label="Debug" width="150px">
            <options>
                <option label="None" value="0"  default="true" />
                <option label="Python Only" value="2"/>
                <option label="Basic Debugging" value="62"/>
                <option label="Basic+Messages" value="126"/>
                <option label="Connections Only" value="16"/>
                <option label="Connections+Python" value="18"/>
                <option label="Connections+Queue" value="144"/>
                <option label="All" value="-1"/>
            </options>
        </param>
    </params>
</plugin>
"""
try:
    import gzip
    import hashlib
    import json
    import re               # Needed to extract data from Some JSON result
    import urllib.parse     # Needed to encode request body messages
#    from datetime import datetime
#    from datetime import timedelta
    import datetime
    import time
    import locale
    import DomoticzEx as Domoticz
except ImportError:
    import fakeDomoticz as Domoticz
    
class BasePlugin:
    httpConn = None
    runAgain = 60
    disconnectCount = 0
    sProtocol = "HTTPS"
   
    def __init__(self):
        return

    def apiRequestGarbage(self): # Needed headers for Data retrieval
        return {
            'Verb' : 'GET',
            'URL'  : '/',
            'Headers' : {   'Content-Type': 'text/xml; charset=utf-8',
                            'Connection': 'keep-alive',
                            'Accept': 'Content-Type: text/html; charset=UTF-8',
                            'Host': Parameters["Address"],
#                            'Origin': self.sProtocol + '://' + Parameters["Address"],
                            'User-Agent':'Domoticz/1.0'
                        }
        }        

    def apiRequestNewPage(self,NewPage):
        return {
            'Verb' : 'GET',
            'URL'  : NewPage,
            'Headers' : {   'Content-Type': 'text/xml; charset=utf-8',
                            'Connection': 'keep-alive',
                            'Accept': 'Content-Type: text/html; charset=UTF-8',
                            'Host': Parameters["Address"],
#                            'Origin': self.sProtocol + '://' + Parameters["Address"],
                            'User-Agent':'Domoticz/1.0'
                        }
        }

    def apiRequestHeaders_cookie(self): # Needed headers for Data retrieval
        return {
            'Verb': 'POST',
            'URL': '/register/zipcode.json',
            'Headers' : {   'Host': Parameters["Address"],
                            'User-Agent': 'python-requests/2.28.1',
                            'Accept': '*/*',
                            'Connection': 'keep-alive',
                            'Cookie': 'CB_SESSION='+self.sessionId,
                            'Content-Type': 'application/x-www-form-urlencoded'    
                    },
            'Data': 'authenticityToken='+self.serverId+'&zipCode='+self.postcode+'&number='+self.street_number
        }

    def apiRequestCalendar(self): # Get calendar
        return {
            'Verb': 'GET',
            'URL': '/afvalkalender.json?from='+self.startDate+'&till='+self.endDate,
            'Headers' : {   'Host': Parameters["Address"],
                            'User-Agent': 'python-requests/2.28.1',
                            'Accept-Encoding': 'gzip, deflate',
                            'Accept': '*/*',
                            'Connection': 'keep-alive',
                            'Content-Type': 'application/json',    
                            'Cookie': 'CB_SESSION='+self.sessionId
                        }
        }

    def onStart(self):
        self.postcode = Parameters["Mode1"]
        self.street_number = Parameters["Mode2"] 
        if Parameters["Mode6"] != "0":
            Domoticz.Debugging(int(Parameters["Mode6"]))
            DumpConfigToLog()
        Domoticz.Log("onStart - Plugin is started.")
        Domoticz.Heartbeat(60)
        # Check if devices need to be created
        createDevices()
        self.httpConn = Domoticz.Connection(Name=self.sProtocol+" Test", Transport="TCP/IP", Protocol=self.sProtocol, Address=Parameters["Address"],Port="443")
        self.httpConn.Connect()

    def onStop(self):
        Domoticz.Log("onStop - Plugin is stopping.")

    def onConnect(self, Connection, Status, Description):
        Domoticz.Debug("Status: "+str(Status)+", Description: "+Description)
        if (Status == 0):
            Domoticz.Log("Connected successfully.")
            Connection.Send(self.apiRequestGarbage() )
        else:
            Domoticz.Log("Failed to connect ("+str(Status)+") to: "+Parameters["Address"]+" with error: "+Description)

    def onMessage(self, Connection, Data):
        if ("Status" in Data):
            Status = int(Data["Status"])        
            Domoticz.Debug("\nStatus = : "+Data["Status"] )
        else:
            Domoticz.Error("No Status in Reply")
            return
            
        Domoticz.Debug("*****Dump start************");
#        DumpHTTPResponseToLog(Data)
        Domoticz.Debug("*****Dump end************\n");

        if (Status == 200):
            if ("Data" not in Data):
                Domoticz.Error("No Data in Reply")
                return

            strData = Data["Data"].decode("utf-8", "ignore")
            gzipped = self.SearchZip(Data)
            Domoticz.Debug("Encode="+str(gzipped));

            LogMessage(strData)
#            Domoticz.Debug("*****************");
#            Domoticz.Debug(strData);
#            Domoticz.Debug("-----------------");

#            apiResponse = json.loads(strData)
#            Domoticz.Debug("Retrieved following json: "+json.dumps(apiResponse))
            try:
                if ('openingstijden' in strData):              
                    Domoticz.Log("Right Webpage found")
                    self.ProcessCookie(Data)                                        # The Cookie is in the RAW Response, not in the JSON
                    if not self.cookieAvailable:
                        Domoticz.Debug("No cookie extracted!")
                    else:
                        Domoticz.Debug("Request Data with retrieved cookie!")
                        Connection.Send(self.apiRequestHeaders_cookie() )                    

                elif ('flashMessage' in strData):              
                    Domoticz.Log("Succesvol ingelogd")
                    apiResponse = json.loads(strData)
#                    Domoticz.Debug("Retrieved following json: "+json.dumps(apiResponse))
                    Domoticz.Debug("flashMessage="+apiResponse["flashMessage"])
                    if apiResponse["flashMessage"] != "":
                        authenticationUrl = ""
                        for address in apiResponse["customData"]["addresses"]:
                            if re.search(' '+self.street_number, address["address"]) != None:
                                authenticationUrl = address["authenticationUrl"]
                                break
                        Domoticz.Debug("Url="+authenticationUrl)

                    self.ProcessCookie(Data)                                        # The Cookie is in the RAW Response, not in the JSON
                    if not self.cookieAvailable:
                        Domoticz.Debug("No cookie extracted!")
                    else:
                        Domoticz.Debug("Request Data with retrieved cookie!"+ self.sessionId)

                    self.startDate = (datetime.datetime.today() - datetime.timedelta(days=0)).strftime("%Y-%m-%d")
                    self.endDate   =  (datetime.datetime.today() + datetime.timedelta(days=30)).strftime("%Y-%m-%d")
            
                    Connection.Send(self.apiRequestCalendar() )                    
                elif (gzipped == "gzip"):            
                    dataresponse = gzip.decompress(Data["Data"])
#                    data = str(data,'utf-8')
                    dataresponse = dataresponse.decode("utf-8", "ignore")
                    Domoticz.Log("Afvaldata unzipped");
                    if not 'customData' in dataresponse: 
                        Domoticz.Log("Garbage not found")
                        return
                    apiResponse = json.loads(dataresponse)
                    Domoticz.Debug("Retrieved following json: "+json.dumps(apiResponse))
#                    Domoticz.Debug(dataresponse)
                    multlist = []
                    for item in apiResponse['customData']['response']['garbage']:
                        if (item['code'] != "KERST"):
                            Domoticz.Log(item['code'] + ": " + item['dates'][0])
                            multlist.append([item['code'],item['dates'][0]])
                    sortedlist = sorted(multlist, key=lambda x: x[1])
                    GarbageString = ""
                    try:
                        locale.setlocale(locale.LC_TIME, 'nl_NL.utf8')
                    except Exception:
                        Domoticz.Error("Locale error, nl_NL.utf8 not installed")
                    for i in sortedlist:
                        datetimeobj = datetime.datetime(*(time.strptime(i[1],'%Y-%m-%d' )[0:6]))
#                        datetimeobj = datetime.strptime(i[1], '%Y-%m-%d')  # TypeError ?
                        GarbageString += datetimeobj.strftime("%a %d %B") + ": " + i[0] + "\n\r"
                    UpdateDevice(UnitName="Garbage", Unit=1, nValue = 0,sValue=GarbageString)
                    GarbageToday = False
                    datetimeobj = datetime.datetime(*(time.strptime(sortedlist[0][1],'%Y-%m-%d' )[0:6]))
                    GarbageAlert = sortedlist[0][0] + "\n\r" + datetimeobj.strftime("%A %d %B")
                    todayend = datetime.datetime.now() + datetime.timedelta(-0.5)  # 21.20
                    todaystart = datetime.datetime.now() + datetime.timedelta(-0.25)  # 6.00
                    tomorrow = datetime.datetime.now() + datetime.timedelta(0.1)	# 21.20
                    tomorrow1 = datetime.datetime.now() + datetime.timedelta(1)  # 22.40 prev day
                    if (sortedlist[0][1] == str(todayend.date())):
                        AlertLevel = 0
                    elif (sortedlist[0][1] == str(todaystart.date())):
                        AlertLevel = 4
                        GarbageToday = True
                    elif (sortedlist[0][1] == str(tomorrow.date())):
                        AlertLevel = 1
                        GarbageToday = True
                    elif (sortedlist[0][1] == str(tomorrow1.date())):
                        AlertLevel = 2
                    else:
                        AlertLevel = 0
                    Domoticz.Log(sortedlist[0][1] + " " + str(todaystart.date()) + " " + str(todayend.date()) + " " + str(tomorrow.date()) + " " + str(tomorrow1.date()))
                    #domoticz.ALERTLEVEL_GREY, ALERTLEVEL_GREEN, ALERTLEVEL_YELLOW, ALERTLEVEL_ORANGE, ALERTLEVEL_RED
                    UpdateDevice(UnitName="Garbage alert", Unit=2, nValue=AlertLevel, sValue=GarbageAlert )              
                    UpdateDevice(UnitName="Garbage today", Unit=3, nValue=GarbageToday, sValue = "" )              
 
                    self.httpConn.Disconnect()

                else:
                    Domoticz.Debug("Not received anything usefull!")
            except KeyError:
                Domoticz.Debug("No defined keys found!")
        
        
        elif (Status == 302):
            Domoticz.Log("Google returned a Page Moved Error.") 
            Domoticz.Debug("Page moved to : "+Data["Headers"]["location"])
            Connection.Send(self.apiRequestNewPage(Data["Headers"]["location"]) )
        elif (Status == 400):
            Domoticz.Error("Bad Request Error.")
        elif (Status == 500):
            Domoticz.Error("Server Error.")
        else:
            Domoticz.Error("Server error: "+str(Status))

    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Debug("onCommand called for Unit " + str(Unit) + ": Parameter '" + str(Command) + "', Level: " + str(Level))

    def onDisconnect(self, Connection):
        Domoticz.Log("onDisconnect called for connection to: "+Connection.Address+":"+Connection.Port)

    def onHeartbeat(self):
        #Domoticz.Trace(True)
        Domoticz.Debug("onHeartbeat")
        if (self.httpConn != None and (self.httpConn.Connecting() or self.httpConn.Connected())):
            Domoticz.Debug("onHeartbeat called, Connection is alive.")
        else:
            self.runAgain = self.runAgain - 1
            if self.runAgain <= 0:
                if (self.httpConn == None):
                    self.httpConn = Domoticz.Connection(Name=self.sProtocol+" Test", Transport="TCP/IP", Protocol=self.sProtocol, Address=Parameters["Address"], Port="443")
                self.httpConn.Connect()
                self.runAgain = 60
            else:
                Domoticz.Debug("onHeartbeat called, run again in "+str(self.runAgain)+" heartbeats.")
        #Domoticz.Trace(False)

    def ProcessCookie(self, httpDict):
        if isinstance(httpDict, dict):            
            Domoticz.Debug("Analyzing Data ("+str(len(httpDict))+"):")
            for x in httpDict:
                if isinstance(httpDict[x], dict):
                    if (x == "Headers"):
                        Domoticz.Debug("---> Headers found")    
                        for y in httpDict[x]:
                            Domoticz.Debug("------->'" + y + "':'" + str(httpDict[x][y]) + "'")
                            if (y == "set-cookie"):
                                Domoticz.Debug("------->"+str(httpDict[x][y])) 
                                Domoticz.Debug("---> Process Cookie Started")
                                try:
                                    self.sessionId = re.search(r"(?<=CB_SESSION=).*?(?=;)", str(httpDict[x][y])).group(0)
#                                   Domoticz.debug(re.search(r"CB_SESSION", str(httpDict[x][y]))
                                    Domoticz.Debug("---> SessionID found: "+ str(self.sessionId)) 
                                    self.cookieAvailable = True
                                except AttributeError:
                                    self.cookieAvailable = False
                                    Domoticz.Debug("---> CB_Session NOT found") 

                                if self.cookieAvailable:
                                    try:
                                        self.serverId = re.search(r"__AT=(.*)&___TS=", str(httpDict[x][y])).group(1)
                                        Domoticz.Debug("---> ServerID found: "+ str(self.serverId)) 
                                    except AttributeError:
                                        self.cookieAvailable = False
                                        Domoticz.Debug("---> ServerID NOT found") 
    def SearchZip(self, httpDict):
        if isinstance(httpDict, dict):            
            for x in httpDict:
                if isinstance(httpDict[x], dict):
                    if (x == "Headers"):
#                        Domoticz.Debug("---> Headers found")    
                        for y in httpDict[x]:
                            if (y == "content-encoding"):
                                Domoticz.Debug("content-encoding="+str(httpDict[x][y])) 
                                return str(httpDict[x][y])
                                
global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def onMessage(Connection, Data):
    global _plugin
    _plugin.onMessage(Connection, Data)

def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)

def onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile):
    global _plugin
    _plugin.onNotification(Name, Subject, Text, Status, Priority, Sound, ImageFile)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

# Generic helper functions
def LogMessage(Message):
    if Parameters["Mode6"] == "File":
        f = open(Parameters["HomeFolder"]+"http.html","w")
        f.write(Message)
        f.close()
        Domoticz.Log("File written")

def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug( "'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for DeviceName in Devices:
        Device = Devices[DeviceName]
        Domoticz.Debug("Device ID:       '" + str(Device.DeviceID) + "'")
        Domoticz.Debug("--->Unit Count:      '" + str(len(Device.Units)) + "'")
        for UnitNo in Device.Units:
            Unit = Device.Units[UnitNo]
            Domoticz.Debug("--->Unit:           " + str(UnitNo))
            Domoticz.Debug("--->Unit Name:     '" + Unit.Name + "'")
            Domoticz.Debug("--->Unit nValue:    " + str(Unit.nValue))
            Domoticz.Debug("--->Unit sValue:   '" + Unit.sValue + "'")
            Domoticz.Debug("--->Unit LastLevel: " + str(Unit.LastLevel))
    return

def DumpHTTPResponseToLog(httpResp, level=0):
    if (level==0): Domoticz.Debug("HTTP Details ("+str(len(httpResp))+"):")
    indentStr = ""
    for x in range(level):
        indentStr += "----"
    if isinstance(httpResp, dict):
        for x in httpResp:
            if not isinstance(httpResp[x], dict) and not isinstance(httpResp[x], list):
                Domoticz.Debug(indentStr + ">'" + x + "':'" + str(httpResp[x]) + "'")
            else:
                Domoticz.Debug(indentStr + ">'" + x + "':")
                DumpHTTPResponseToLog(httpResp[x], level+1)
    elif isinstance(httpResp, list):
        for x in httpResp:
            Domoticz.Debug(indentStr + "['" + x + "']")
    else:
        Domoticz.Debug(indentStr + ">'" + x + "':'" + str(httpResp[x]) + "'")
        
def UpdateDevice(UnitName, Unit, nValue, sValue):
    # Make sure that the Domoticz device still exists (they can be deleted) before updating it 
    if (UnitName in Devices):
    	if (Devices[UnitName].Units[Unit].nValue != nValue) or (Devices[UnitName].Units[Unit].sValue != sValue):
        	Devices[UnitName].Units[Unit].nValue = nValue
        	Devices[UnitName].Units[Unit].sValue = sValue
        	Devices[UnitName].Units[Unit].Update(Log=True)        
#        	Domoticz.Log("Update "+UnitName)
        	Domoticz.Log("Update "+UnitName + " = " + sValue + " " + str(nValue))
    return


#############################################################################
#                       Device specific functions                           #
#############################################################################

def createDevices():

    # Give the devices a unique unit number. This makes updating them more easy.
#    if (len(Devices) == 0):
    if (not "Garbage" in Devices):
        GarbageUnit = Domoticz.Unit(Name="Garbage", Unit=1, TypeName="Text", DeviceID="Garbage").Create()
        Domoticz.Log("Garbage Device created.")        
    if (not "Garbage alert" in Devices):
        Domoticz.Unit(Name="Garbage alert", Unit=2, TypeName="Alert",  DeviceID="Garbage alert" ).Create()
        Domoticz.Log("Garbage alert created")
    if (not "Garbage today" in Devices):
        Domoticz.Unit(Name="Garbage today", Unit=3, TypeName="Switch",  DeviceID="Garbage today" ).Create()
        Domoticz.Log("Garbage today created")
