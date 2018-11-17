from opentuner.search import technique

class BasicHistoryRead(technique.SequentialSearchTechnique):
  """ Read from sub-DB to reconstruct history """
  def __init__(self, points, database, *pargs, **kwargs):
    """
    read points from data base
    """
    super(BasicHistoryRead, self).__init__(*pargs, **kwargs)
    self.points = points
    self.database = database

  def main_generator(self):

    objective   = self.objective
    driver      = self.driver
    manipulator = self.manipulator

    # read from sub-db and return the cfg
    import sqlite3, sys
    dbconn = sqlite3.connect(self.database)
    c = dbconn.cursor()
    c.execute("SELECT * FROM res")

    data = c.fetchall()
    names = list(map(lambda x: x[0], c.description))
    center = driver.get_configuration(manipulator.random())

    for row in data:
      new_cfg = manipulator.copy(center.data)
      for param in manipulator.parameters(center.data):
        if param.is_primitive():
          unit_value = param.get_unit_value(new_cfg.data)
          # print "unit:", unit_value

        # manipulate complex parameter
        else:
          # print "name:", param.name
          param.set_value(new_cfg, row[names.index(param.name)])
      yield driver.get_configuration(new_cfg)

    # for row in data:
    #   for index, key in enumerate(center):
    #     idx = names.index(key)
    #     center[key] = row[idx]
    #   yield driver.get_configuration(center)

    # default in random fashion
    while True:
      print('[WARNING] random for readHistory')
      yield driver.get_configuration(manipulator.random())

# read database and history
import os, glob
try:
  num = glob.glob('sub-db-*.db')[0].replace('.db', '').split('-')[-1]
  fileName = os.path.join(os.getcwd(), glob.glob('sub-db-*.db')[0])
except:
  num, fileName = 0, None

# register our new technique in global list
technique.register(BasicHistoryRead(num, fileName))
