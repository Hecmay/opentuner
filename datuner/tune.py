import sys
import adddeps
import argparse
import opentuner
from opentuner import ConfigurationManipulator
from opentuner import EnumParameter
from opentuner import FloatParameter
from opentuner import IntegerParameter
from opentuner import MeasurementInterface
from opentuner import Result
import socket
import pickle
import os
from setup import *

class ProgramTuner(ProgramTunerWrapper):

  if os.path.exists(os.getcwd() + '/vtr.py'):
    from vtr import designdir
    from vtr import archdir
    from vtr import vtrpath
    from vtr import workspace
#    from vtr import target_cp
  elif os.path.exists(os.getcwd() + '/vivado.py'):
    from vivado import top_module
  elif os.path.exists(os.getcwd() + '/quartus.py'):
    from quartus import top_module
    from quartus import target_family
    from quartus import target_device
  elif os.path.exists(os.getcwd() + '/qpro.py'):
    from qpro import top_module
    from qpro import target_family
    from qpro import target_device
  elif os.path.exists(os.getcwd() + '/custom.py'):
    import custom

  param = pickle.load(open('space.p', 'rb'))
  if os.path.isfile('sweep.p'):
    sweep, genfile = pickle.load(open('sweep.p', 'rb'))

  try:
    # read into the cfg-qor in sub-db
    import glob, sqlite3
    num = glob.glob('sub-db-*.db')[0].replace('.db', '').split('-')[-1]
    fileName = os.path.join(os.getcwd(), glob.glob('sub-db-*.db')[0])

    # connect and query data in sub-db
    conn = sqlite3.connect(fileName)
    cur = conn.cursor()
    cur.execute("SELECT * FROM res")
    rows = cur.fetchall()
    names = list(map(lambda x: x[0], cur.description))
  except:
    rows = []

  def manipulator(self):
    manipulator = ConfigurationManipulator()
    for item in self.param:
      param_type, param_name, param_range = item
      if param_type == 'EnumParameter':
        manipulator.add_parameter(EnumParameter(param_name, param_range))
      elif param_type == 'IntegerParameter' :
        manipulator.add_parameter(IntegerParameter(param_name, param_range[0], param_range[1]))
      elif param_type == 'FloatParameter' :
        manipulator.add_parameter(FloatParameter(param_name, param_range[0], param_range[1]))
    return manipulator

  def save_final_config(self, configuration):
    """called at the end of tuning"""
    cfg = configuration.data
    print "Optimal options written to bench_config.json:", cfg
    self.manipulator().save_to_file(cfg, 'inline_config.json')
    f = open('./localresult.txt','rb')
    res = 0
    msg = []
    metadata = []
    config = ''
    for key in cfg:
      msg.append([key, cfg[key]])
      config = config + str(key) + ',' + str(cfg[key]) + ','
    config = config[:-1]

    #while True:
    #  line = f.readline()
    #  if not line: break
    #  if config in line:
    #    a = line.split(",")
    #    a[-1] = float(a[-1][:-1])
    #    res = a[-1]
    #    metadata = a[len(msg)*2:-1]

    lines = f.readlines()
    line = lines[-1]
    a = line.split(",")
    res = float(a[-1])
    metadata = a[len(msg)*2:-1]

    f.close()

    #f = open('./guide.txt','rb')
    #guideline = f.readline()
    #f.close()
#    pickle.dump([msg, metadata, res, guideline], open('result.p', 'wb'))
    pickle.dump([msg, metadata, res], open('result.p', 'wb'))

  def dumpresult(self, cfg, res, metadata = []):
#  def dumpresult(self, cfg, res, guideline):
    """
    Compile and run a given configuration then
    return performance
    """
    f = open('./localresult.txt', 'a')
    for key in cfg:
      f.write(str(key) + "," + str(cfg[key]) + ",")
    f.write(','.join(str(i) for i in metadata) + ',')
    f.write(str(res))
    f.write('\n')
    f.close()

    #try: #currently in try catch because it only works for some vtr flows
    #  f = open('./guide.txt','w') #overwrite for ease
    #  f.write(guideline)
    #  f.close()
    #except:
    #  pass

if __name__ == '__main__':
  argparser = opentuner.default_argparser()
  ProgramTuner.main(argparser.parse_args())
