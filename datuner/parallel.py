#!/usr/bin/env python
from __future__ import print_function
import os, sys, subprocess, argparse, time, pickle
from mpi4py import MPI

design_name = "diffeq1"

def distTask(hostname, parallel, subspace):
    """ distribute tasks over cluster """

    # setup the workspace for each machine (pwd)
    workspace = os.path.join(os.getcwd(), hostname)
    if os.path.isdir(workspace): os.system('rm -rf ' + workspace)
    os.system('mkdir -p ' + workspace)
    os.system('cp files/parallel.py ' + workspace)
    os.chdir(workspace)

    cmd  = "mpiexec --prefix /home/sx233/ -n " + str(parallel + 1)
    cmd += " -host " + hostname

    # output from processes into files (out.rank)
    cmd += " --output-filename " + workspace + "/out"
    cmd += " python parallel.py"

    # passed in params
    param  = " -p " + str(parallel + 1)
    param += " -w " + str(workspace)
    cmd   += param

    # pickle subspace for main()
    pickle.dump(subspace, open("subspace.p", "wb"))

    # process level parallelism running main()
    p = subprocess.Popen(cmd,stdout=subprocess.PIPE, stderr=subprocess.STDOUT, shell=True)
    p.communicate()

    try:
      data = readData(parallel, workspace)
    except:
      data = [[['0', '1', '2'], [3, 4, 5], 999999]]
    return data


def readData(parallel, workspace):
    """ get [cfg, qor, guideline] from out.rank
        return data = [[cfg1, qor1, guidelien1],...]
    """
    cfg, res, guideline, data = 0, 0, [], []
    #for index in range(parallel):
    #    outputPath = os.path.join(workspace, "out." + str(index))
    #    with open(outputPath, "r") as f:
    #        content = f.readlines()
    #        print(content)
    subprocess.Popen('ls', shell=True)
    data = pickle.load(open('jobs_results.p', 'rb'))
    return data


def enum(*sequential, **named):
    enums = dict(zip(sequential, range(len(sequential))), **named)
    return type('Enum', (), enums)


def main(parallel, workspace):
    # define MPI message tags
    tags = enum('READY', 'DONE', 'EXIT', 'START')

    # initializations and preliminaries
    comm = MPI.COMM_WORLD   # get MPI communicator object
    size = comm.size        # total number of processes
    rank = comm.rank        # rank of this process
    status = MPI.Status()   # get MPI status object

    if rank == 0:
        tasks = range(1*size)
        task_index = 0
        num_workers = size - 1
        closed_workers = 0
        results = []

        while closed_workers < num_workers:

            data = comm.recv(source=MPI.ANY_SOURCE, tag=MPI.ANY_TAG, status=status)
            source = status.Get_source()  # the rank of sender
            tag = status.Get_tag()        # the status of the node

            if tag == tags.READY:

                # send task if node ready to work
                if task_index < len(tasks):
                    comm.send(tasks[:task_index], dest=source, tag=tags.START)
                    task_index += 1
                else:
                    comm.send(None, dest=source, tag=tags.EXIT)

            # collect data when task finished
            elif tag == tags.DONE:
                results.append(data)
                print("Got data from worker %d" % source)
                print("data is %s" % data)

            elif tag == tags.EXIT:
                print("Worker %d exited." % source)
                closed_workers += 1

        pickle.dump(results, open("jobs_results.p", "wb"))
        print("Master finishing")

    else:

        # get the hostname
        name = MPI.Get_processor_name()

        while True:
            comm.send(None, dest=0, tag=tags.READY)

            # stall before recv any task (subspace)
            task = comm.recv(source=0, tag=MPI.ANY_TAG, status=status)
            tag = status.Get_tag()

            # invoke model tuning and prediction
            if tag == tags.START:
                print("current path: %s" % workspace)
                os.chdir(workspace)
                subspace = pickle.load(open('subspace.p', 'rb'))
                cfg, res, guideline = tune(os.getcwd(), design_name, rank, subspace)
                result = [cfg, res, guideline]
                print("This is %d and result: %s" % (rank, result))
                comm.send(result, dest=0, tag=tags.DONE)

            # break after recv exit signal from master
            elif tag == tags.EXIT:
                break

        # send the exit status and exit
        comm.send(None, dest=0, tag=tags.EXIT)


def tune(pwd, design_name, i, space):
    os.system('mkdir -p ' + str(i))
    os.system('cp ../package.zip ' + str(i))
    os.chdir('./' + str(i))
    os.system('unzip -o package.zip')
    os.system('rm package.zip')
    pickle.dump(space, open('space.p', 'wb'))
    my_env = os.environ.copy()
    my_env["PATH"] = "/scratch/common/tools/quartus_17.0/quartus/bin:/scratch/common/tools/quartus_17.0/modelsim_ase/bin:" + my_env["PATH"]
    p = subprocess.Popen("python tune.py --test-limit=0 --parallelism=1", shell=True, env=my_env)
    p.communicate()
    try:
      cfg, metadata, res = pickle.load(open('result.p', 'rb'))
    except:
      cfg, metadata, res = [[0,0], [0,0]], [-1, -1, -1, -1], -1
    return [cfg, metadata, res]


def unified(pwd, design_name, i, space):
    import numpy as np

    # set up tmp work space for each process
    os.system('mkdir -p ' + str(i))
    os.system('cp ../package.zip ' + str(i))
    os.chdir('./' + str(i))
    os.system('unzip -o package.zip')
    os.system('rm package.zip')
    pickle.dump(space, open('space.p', 'wb'))

    # reconstruct the sub-db
    # TODO: checking required
    os.system('cp ../../results.db .')
    conn = sqlite3.connect('results.db')
    cur = conn.cursor()
    cur.execute("SELECT * FROM res")
    rows = cur.fetchall()
    os.system('mv results.db sub-db-' + len(rows) + '.db')

    pwd = "/home/sx233/datuner-ml/test/diffeq1"
    design_name = "diffeq1"

    model_routability = pickle.load(open(pwd + '/routability_' + design_name + '.dat', 'rb'))
    model = pickle.load(open(pwd + '/xgb_' + design_name + '.dat', 'rb'))

    p = subprocess.Popen("python tune1.py --test-limit=0 --parallelism=1", shell=True)
    p.communicate()
    cfg, res, guideline = pickle.load(open('result1.p', 'rb'))
    for j in range(0, len(guideline)):
      guideline[j] = float(guideline[j])
    test_x = np.array(guideline)
    test_x = np.reshape(test_x, (1,-1))
    y_routability = model_routability.predict(test_x)
    if y_routability == 1:

      ##########
      pred = model.predict(test_x)
      if pred == 0 or pred == 1 or pred == 2:
        decision = "accept"
      else:
        decision = "reject"
      ##########

      if decision == "reject":
        res = float(10*pred)
        guideline = ""
      elif decision == "accept":
        pickle.dump(cfg, open('best.p', 'wb'))
        p = subprocess.Popen("python tune2.py", shell=True)
        p.communicate()
        cfg, res, guideline = pickle.load(open('result2.p', 'rb'))

    elif y_routability == 0:
      res = 777777
      guideline = ""

    return cfg, res, guideline


# launched by mpiexec python script
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Mpi4py test')
    parser.add_argument('-w', '--workspace',  type=str, dest='ws')
    parser.add_argument('-p', '--parallel', type=int, dest='pf')
    args = parser.parse_args()
    main(args.pf, os.getcwd())
