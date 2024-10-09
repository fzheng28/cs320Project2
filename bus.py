#project: P2


from math import sin, cos, asin, sqrt, pi
from datetime import datetime
from zipfile import ZipFile
import matplotlib, pandas as pd
from pandas import Series, DataFrame
from matplotlib import pyplot as plt

def haversine_miles(lat1, lon1, lat2, lon2):
    """Calculates the distance between two points on earth using the
    harversine distance (distance between points on a sphere)
    See: https://en.wikipedia.org/wiki/Haversine_formula

    :param lat1: latitude of point 1
    :param lon1: longitude of point 1
    :param lat2: latitude of point 2
    :param lon2: longitude of point 2
    :return: distance in miles between points
    """
    lat1, lon1, lat2, lon2 = (a/180*pi for a in [lat1, lon1, lat2, lon2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon/2) ** 2
    c = 2 * asin(min(1, sqrt(a)))
    d = 3956 * c
    return d

class Location:
    """Location class to convert lat/lon pairs to
    flat earth projection centered around capitol
    """
    capital_lat = 43.074683
    capital_lon = -89.384261

    def __init__(self, latlon=None, xy=None):
        if xy is not None:
            self.x, self.y = xy
        else:
            # If no latitude/longitude pair is given, use the capitol's
            if latlon is None:
                latlon = (Location.capital_lat, Location.capital_lon)

            # Calculate the x and y distance from the capital
            self.x = haversine_miles(Location.capital_lat, Location.capital_lon,
                                     Location.capital_lat, latlon[1])
            self.y = haversine_miles(Location.capital_lat, Location.capital_lon,
                                     latlon[0], Location.capital_lon)

            # Flip the sign of the x/y coordinates based on location
            if latlon[1] < Location.capital_lon:
                self.x *= -1

            if latlon[0] < Location.capital_lat:
                self.y *= -1

    def dist(self, other):
        """Calculate straight line distance between self and other"""
        return sqrt((self.x - other.x) ** 2 + (self.y - other.y) ** 2)

    def __repr__(self):
        return "Location(xy=(%0.2f, %0.2f))" % (self.x, self.y)

class BusDay: 
    def __init__(self, date_input):                     
        self.day_of_week = date_input.strftime("%A").lower()
        self.date = int(date_input.strftime("%Y%m%d"))
        self.service_ids = self.service_ids()
        self.trip = self.__get_trips()
        self.stop = self.__stops()
        self.node = Node(self.stop, 0)
        self.list = []
    
    @staticmethod
    def df(file):
        with ZipFile('mmt_gtfs.zip') as zf:
            with zf.open(file) as f:
                df = pd.read_csv(f)
        return df
    
    def service_ids(self):
        df_calendar = self.df("calendar.txt")
        condition_1=(df_calendar[self.day_of_week]==1)
        condition_2=(df_calendar['start_date']<=self.date) & (df_calendar['end_date']>=self.date)
        service_list=[]
        service_list = [i for i in df_calendar[condition_1 & condition_2]['service_id'] if i not in service_list]
        service_list.sort()
        return service_list
    
    def get_trips(self, route_id=None):
        route_list = []
        if route_id == None:
            return self.trip
        else:
            for i in self.trip:
                if i.route_id == route_id:
                    route_list.append(i)
        return route_list
    
    def __get_trips(self):
        trip_df = self.df("trips.txt")
        trips = []
        for rows in trip_df[trip_df.service_id.isin(self.service_ids)].itertuples():
            trip_no = rows[4]
            short_name = rows[2]
            bikes =  rows[14]==1
            trips.append(Trip(trip_no, short_name,bikes))
        return sorted(trips, key=lambda x: x.trip_id)
    
    def get_stops(self):
        return self.stop

    def __stops(self):
        stoptime_df = self.df("stop_times.txt") 
        trip_id_list = [i.trip_id for i in self.trip]
        stop_list = stoptime_df[stoptime_df.trip_id.isin(trip_id_list)].stop_id.tolist()
        stop_df = self.df("stops.txt")
        sorted_df = stop_df[stop_df.stop_id.isin(stop_list)]
        stop_object_list = []
        for rows in sorted_df.itertuples():
            stop_id = rows[1]
            location = Location(latlon = (rows[5], rows[6]))
            wheelchair = rows[13]==1
            stop_object_list.append(Stop(stop_id, location, wheelchair))
        return sorted(stop_object_list, key=lambda x: x.stop_id)
            
    def get_stops_rect(self, lim1, lim2, node=None):
        rect_list = []
        if node == None:
            node = self.node
        if node.split_level == 6:
            new = [i for i in node.val if (i.loc.x>=min(lim1)) & (i.loc.x <= max(lim1)) & (i.loc.y>=min(lim2)) & (i.loc.y <= max(lim2))]
            return new
        if node.split_level%2 == 0:  
            if node.val > min(lim1):
                rect_list.extend(self.get_stops_rect(lim1,lim2,node=node.left))
            if node.val < max(lim1):
                rect_list.extend(self.get_stops_rect(lim1,lim2,node=node.right))
        else:
            if node.val > min(lim2):
                rect_list.extend(self.get_stops_rect(lim1,lim2,node=node.left))
            if node.val < max(lim2):
                rect_list.extend(self.get_stops_rect(lim1,lim2,node=node.right))
        return rect_list
    
    def get_stops_circ(self, center, radius):
        rect_list = self.get_stops_rect((center[0]-radius,center[0]+radius),(center[1]-radius,center[1]+radius))
        x = [i for i in rect_list if ((i.loc.x-center[0])**2 + (i.loc.y-center[1])**2 ) <= radius**2]
        return x

    def scatter_stops(self, ax):
        df=pd.DataFrame([x.__dict__ for x in self.stop])
        x = []
        y = []
        for i in df.itertuples():
            x.append(i[2].x)
            y.append(i[2].y)
        df['x']=x
        df['y']=y

        df_1 =df[df['wheelchair_boarding']==True]
        ax_1 = df_1.plot.scatter(x='x', y='y', color='red',ax=ax,s=2)

        df_2 =df[df['wheelchair_boarding']==False]
        df_2.plot.scatter(x='x', y='y', color='0.7',ax=ax_1,s=2)
    
    def draw_tree(self, ax, node=None, xlim=None, ylim=None):
        if node==None:
            node=self.node
            xlim=(-8,8)
            ylim=(-8,8)
        if node.split_level==6:
            return
        if node.split_level%2==0:
            ax.plot((node.val,node.val), ylim, lw=5, color="green")
            self.draw_tree(ax=ax,node=node.left, xlim=(xlim[0],node.val) , ylim=ylim)
            self.draw_tree(ax=ax,node=node.right, xlim=(node.val,xlim[1]), ylim=ylim)
        else:
            ax.plot(xlim,(node.val,node.val), lw=5, color="green")
            self.draw_tree(ax=ax, node=node.left, xlim=xlim , ylim=(ylim[0],node.val ))
            self.draw_tree(ax=ax, node=node.right, xlim=xlim , ylim=(node.val,ylim[0]) )
            
class Trip:
    def __init__(self, trip_id, route_id, bikes_allowed):
        self.trip_id = trip_id
        self.route_id = route_id
        self.bikes_allowed = bikes_allowed
    
    def __repr__(self):
        return "Trip("+str(self.trip_id)+", " + str(self.route_id)+", " + str(self.bikes_allowed)+")"
        
class Stop:
    def __init__(self, stop_id, location, wheelchair_boarding):
        self.stop_id = stop_id
        self.loc = location
        self.wheelchair_boarding = wheelchair_boarding
    def __repr__(self):
        return "Stop("+str(self.stop_id)+", " + str(self.loc)+", " + str(self.wheelchair_boarding)+")"
    
class Node:
    def __init__(self, stops, split_level):
        self.split_level = split_level
        if split_level < 6:
            if split_level%2==0:
                sorted_stops = sorted(stops, key=lambda i: i.loc.x)
                self.val = sorted_stops[len(sorted_stops)//2].loc.x
            else: 
                sorted_stops = sorted(stops, key=lambda i: i.loc.y)
                self.val = sorted_stops[len(sorted_stops)//2].loc.y
            stop_left = sorted_stops[:len(sorted_stops)//2]
            stop_right = sorted_stops[len(sorted_stops)//2:]
            self.left = Node(stop_left, split_level+1)
            self.right = Node(stop_right, split_level+1)
        else:
            self.val = stops
            return    
