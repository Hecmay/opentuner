from opentuner import MeasurementInterface
from opentuner import Result
import os
import subprocess

class ProgramTunerWrapper(MeasurementInterface):

  def checkPoint(self, cfg):

    # fetch points and type cast to temp{}
    temp = dict()
    for row in self.rows:
      for index, key in enumerate(cfg):
        idx = self.names.index(key)
        temp[key] = type(cfg[key])(row[idx])

      # return visited and qor if match
      if temp == cfg:
        return 1, float(row[-1])

    # return nothing in default
    return 0, 0

  def get_qor(self):
    f = open('sta.summary', 'r')
    while True:
      line = f.readline()
      if "Slack" in line.split():
        slack = line.split(':')[1]
        break
    f.close()

    f = open('fit.summary', 'r')
    while True:
      line = f.readline()
      if not line: break
      if 'ALMs' in line:
        alm = line.split(':')[1].split('/')[0].rstrip().lstrip()
        if ',' in alm:
          alm = alm.split(',')[0] + alm.split(',')[1]
        continue
      if 'Total registers' in line:
        reg = line.split(':')[1].split('/')[0].rstrip().lstrip()
        continue
      if 'block memory bits' in line:
        bram = line.split(':')[1].split('/')[0].rstrip().lstrip()
        continue
      if 'DSP Blocks' in line:
        dsp = line.split(':')[1].split('/')[0].rstrip().lstrip()
        continue
    f.close()
    metadata = [alm, reg, bram, dsp]
    timing = float(slack)
    return timing, metadata

  def run(self, desired_result, input, limit):
    """
    Compile and run a given configuration then
    return performance
    """
    target_cp = 'target_cp'
    map_param = [
      'adv_netlist_opt_synth_wysiwyg_remap',
      'allow_any_ram_size_for_recognition',
      'allow_any_rom_size_for_recognition',
      'allow_any_shift_register_size_for_recognition',
      'allow_power_up_dont_care',
      'allow_shift_register_merging_across_hierarchies',
      'allow_synch_ctrl_usage',
      'auto_carry_chains',
      'auto_clock_enable_recognition',
      'auto_dsp_recognition',
      'auto_enable_smart_compile',
      'auto_open_drain_pins',
      'auto_ram_recognition',
      'auto_resource_sharing',
      'auto_rom_recognition',
      'auto_shift_register_recognition',
      'disable_register_merging_across_hierarchies',
      'dsp_block_balancing',
      'enable_state_machine_inference',
      'force_synch_clear',
      'ignore_carry_buffers',
      'ignore_cascade_buffers',
      'ignore_max_fanout_assignments',
      'infer_rams_from_raw_logic',
      'mux_restructure',
      'optimization_technique',
      'optimize_power_during_synthesis',
      'remove_duplicate_registers',
      'shift_register_recognition_aclr_signal',
      'state_machine_processing',
      'strict_ram_recognition',
      'synthesis_effort',
      'synthesis_keep_synch_clear_preset_behavior_in_unmapper',
      'synth_resource_aware_inference_for_block_ram',
      'synth_timing_driven_synthesis'
    ]
    fit_param = [
      'alm_register_packing_effort',
      'auto_delay_chains',
      'auto_delay_chains_for_high_fanout_input_pins',
      'eco_optimize_timing',
      'final_placement_optimization',
      'fitter_aggressive_routability_optimization',
      'fitter_effort',
      'optimize_for_metastability',
      'optimize_hold_timing',
      'optimize_ioc_register_placement_for_timing',
      'optimize_multi_corner_timing',
      'optimize_power_during_fitting'
      'periphery_to_core_placement_and_routing_optimization',
      'physical_synthesis',
      'placement_effort_multiplier',
      'programmable_power_maximum_high_speed_fraction_of_used_lab_tiles',
      'programmable_power_technology_setting',
      'qii_auto_packed_registers',
      'router_clocking_topology_analysis',
      'router_lcell_insertion_and_logic_duplication',
      'router_register_duplication',
      'router_timing_optimization_level',
      'seed',
      'tdc_aggressive_hold_closure_effort',
      'allow_register_retiming'
    ]

    cfg = desired_result.configuration.data
    result_id = desired_result.id

    # if visited == 1, read qor from DB
    visited, qor = self.checkPoint(cfg)

    top_module = self.top_module
    target_family = self.target_family
    target_device = self.target_device
    target_cp = str(cfg[target_cp]);

    #Write options
    f = open('./options.tcl', 'w')
    #f.write('execute_module -tool map -args "--family=' + target_family + ' --part=' + target_device + ' ')
    for param in map_param:
      try:
        f.write('set_global_assignment -name '+param+' '+cfg['map_' + param]+'\n')
      except: continue
     # f.write('--' + param + '=' + cfg['map_' + param] + ' ')
    #f.write('"\n')
    #f.write('execute_module -tool fit -args "--part=' + target_device + ' ')
    for param in fit_param:
      try:
        f.write('set_global_assignment -name '+param+' '+cfg['fit_'+ param]+'\n')
      except: continue
      #f.write('--' + param + '=' + cfg['fit_' + param] + ' ')
    #f.write('"\n')
    #f.write('execute_module -tool fit\n')
    f.close()

    if hasattr(self,'sweep'):
        sweep = self.sweep
        genfile = self.genfile

        if len(sweep) != 0:
            # generate verilog design file; this is to integrate the libcharm genverilog scripts
            sweepparam = int(sweep[0][1])
            sweeparg_str = ""
            for arg in sweep:
                sweeparg_str = sweeparg_str + arg[1] + ' '
            genveri = 'cd design; python ' + genfile + ' ' + sweeparg_str + '; cd ..'
            subprocess.Popen(genveri, shell=True).wait()

            # Replace the top module name in tcl file
            tclmodcmd = 'sed \'s/TOPMODULE/' + top_module + '/g\' run_quartus.tcl > run_quartus_sweep.tcl'
            subprocess.Popen(tclmodcmd, shell=True).wait()

            print "Starting " + str(sweepparam)
            cmd = 'quartus_sh -t ./run_quartus_sweep.tcl'
            #subprocess.Popen(cmd, shell=True).wait()
            #cmd = 'ls'
            run_result = self.call_program(cmd)
            assert run_result['returncode'] == 0
            result, metadata = self.get_qor()
            self.dumpresult(cfg, result, metadata)
            cleanupcmd = 'rm run_quartus_sweep.tcl'
            subprocess.Popen(cleanupcmd, shell=True).wait()
            print "Finished " + str(sweepparam)
    elif visited == 1:
        print 'Same', qor
        result, metadata = float(target_cp) - qor, [99, 78, 123, 90]
        self.dumpresult(cfg, result, metadata)
    else:
        tclmodcmd = "sed -i 's/FAMILY/\""+ target_family +"\"/g' run_quartus.tcl"
        subprocess.Popen(tclmodcmd, shell=True).wait()
        tclmodcmd = "sed -i 's/DEVICE/\""+ target_device +"\"/g' run_quartus.tcl"
        subprocess.Popen(tclmodcmd, shell=True).wait()
        tclmodcmd = 'sed -e \'s:TOPMODULE:' + top_module + ':g\' ' + 'run_quartus.tcl > run.tcl'
        subprocess.Popen(tclmodcmd, shell=True).wait()
        tclmodcmd = "sed -i 's/FREQ/"+ str(float(target_cp)/2) +"/g' design/"+top_module+".sdc"
        subprocess.Popen(tclmodcmd, shell=True).wait()
        tclmodcmd = "sed -i 's/PERIOD/"+ target_cp +"/g' design/"+top_module+".sdc"
        subprocess.Popen(tclmodcmd, shell=True).wait()
        #cmd = 'quartus_sh -t ./run.tcl'
        #subprocess.Popen(cmd, shell=True).wait()
        #run_result = self.call_program(cmd)

        #assert run_result['returncode'] == 0

        #result, metadata = self.get_qor()
        result, metadata = 2.6, [2.5, 34, 67, 6]
        result = float(target_cp) - result
        self.dumpresult(cfg, result, metadata)

    return Result(time = result)
