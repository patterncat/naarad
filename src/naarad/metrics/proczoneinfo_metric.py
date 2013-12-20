# coding=utf-8
"""
© 2013 LinkedIn Corp. All rights reserved.
Licensed under the Apache License, Version 2.0 (the "License"); you may not use this file except in compliance with the License. You may obtain a copy of the License at  http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
"""

from collections import defaultdict
import datetime
import gc
import logging
import os
import re
import numpy
from naarad.metrics.metric import Metric
import naarad.utils

logger = logging.getLogger('naarad.metrics.ProcZoneinfoMetric')

class ProcZoneinfoMetric(Metric):
  """
  logs of /proc/vmstat
  The raw log file is assumed to have a timestamp prefix of all lines. E.g. in the format of "2013-01-02 03:55:22.13456 compact_fail 36"
  The log lines can be generated by   'cat /proc/vmstat | sed "s/^/$(date +%Y-%m-%d\ %H:%M:%S.%05N)\t/" '  
  """
  unit = 'pages'  # The unit of the metric. For /proc/zoneinfo, they are all in pages
    
  skipped_sub_metrics = ('protection', 'pagesets', 'cpu:', 'count:', 'high:', 'batch:', 'vm', 'all_unreclaimable:', 'prev_priority:', 'start_pfn:', 'inactive_ratio:') 
  processed_sub_metrics = ('min', 'high', 'scanned','spanned', 'present')
    
  zones = None   # Users can specify which zones to process/plot, e.g. zones= Node.0.zone.DMA
  
  def __init__ (self, metric_type, infile, hostname, output_directory, resource_path, label, ts_start, ts_end, **other_options):
    Metric.__init__(self, metric_type, infile, hostname, output_directory, resource_path, label, ts_start, ts_end)
    
    self.sub_metrics = None
    # in particular, Section can specify a subset of all metrics: sub_metrics=pages.min nr_free_pages

    
    for (key, val) in other_options.iteritems():
      setattr(self, key, val.split())   
      
    self.metric_description = {
      'nr_free_pages': 'Number of free pages',
      'nr_inactive_anon': 'Number of inactive anonymous pages',
      'nr_active_anon': 'Number of active anonymous pages',
      'nr_inactive_file': 'Number of inactive file cache pages',
      'nr_active_file': 'Number of active file cache pages',
     }    

      
  def parse(self):
    """
    Parse the vmstat file
    :return: status of the metric parse
    """
    logger.info('Processing : %s',self.infile)
    file_status = naarad.utils.is_valid_file(self.infile)
    if not file_status:
      return False      
   
    status = True    
    cur_zone = None
    cur_submetric = None
    cur_value = None
    
    with open(self.infile) as fh:
      data = {}  # stores the data of each column
      for line in fh:
        words = line.replace(',',' ').split()           # [0] is day; [1] is seconds; [2...] is field names:;        
        
        if len(words) < 3:
          continue
          
        ts = words[0] + " " + words[1]
        if self.ts_out_of_range(ts):
          continue
          
        if words[2] == 'Node':  # Node 0 zone      DMA
          cols = words[2:]
          cur_zone = '.'.join(cols) 
          continue 
        elif words[2] == 'pages':  # pages free     3936
          cur_submetric = words[2] + '.' + words[3]  # pages.free          
          cur_value = words[4]
        elif words[2] in self.processed_sub_metrics:
          cur_submetric = 'pages' + '.' + words[2] # pages.min
          cur_value = words[3]
        elif words[2] in self.skipped_sub_metrics:
          continue   
        else:   #other useful submetrics
          cur_submetric = words[2]
          cur_value = words[3]
      
        col = cur_zone + '.' + cur_submetric  # prefix with 'Node.0.zone.DMA.
        
        #only process zones specified in config
        if cur_zone and self.zones and cur_zone not in self.zones:
          continue
        
        # only process sub_metrics specified in config. 
        if self.sub_metrics and cur_submetric and cur_submetric not in self.sub_metrics:
          continue        
         
        if col in self.column_csv_map: 
          out_csv = self.column_csv_map[col] 
        else:
          out_csv = self.get_csv(col)   #  column_csv_map[] is assigned in get_csv()
          data[out_csv] = []        
         
        data[out_csv].append(ts + "," + cur_value)
    
    #post processing, putting data in csv files;   
    for csv in data.keys():      
      self.csv_files.append(csv)
      with open(csv, 'w') as fh:
        fh.write('\n'.join(data[csv]))

    gc.collect()
    return status
