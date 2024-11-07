'''
Analysis utilities for flow analysis
'''
import ROOT
import os
import sys
import ctypes
from itertools import combinations
import numpy as np

def get_vn_versus_mass(thnSparse, inv_mass_bins, mass_axis, vn_axis, debug=False):
    '''
    Project vn versus mass

    Input:
        - thnSparse:
            THnSparse, input THnSparse obeject (already projected in centrality and pt)
        - inv_mass_bins:
            list of floats, bin edges for the mass axis
        - mass_axis:
            int, axis number for mass
        - vn_axis:
            int, axis number for vn
        - debug:
            bool, if True, create a debug file with the projections (default: False)

    Output:
        - hist_mass_proj:
            TH1D, histogram with vn as a function of mass
    '''
    hist_vn_proj = thnSparse.Projection(vn_axis, mass_axis)
    hist_mass_proj = thnSparse.Projection(mass_axis)
    hist_mass_proj.Reset()
    invmass_bins = np.array(inv_mass_bins)
    hist_mass_proj = ROOT.TH1D('hist_mass_proj', 'hist_mass_proj', len(invmass_bins)-1, invmass_bins)

    if debug:
        outfile = ROOT.TFile('debug.root', 'RECREATE')

    for i in range(hist_mass_proj.GetNbinsX()):
        bin_low = hist_vn_proj.GetXaxis().FindBin(invmass_bins[i])
        bin_high = hist_vn_proj.GetXaxis().FindBin(invmass_bins[i+1])
        profile = hist_vn_proj.ProfileY(f'profile_{bin_low}_{bin_high}', bin_low, bin_high)
        mean_sp = profile.GetMean()
        mean_sp_err = profile.GetMeanError()
        hist_mass_proj.SetBinContent(i+1, mean_sp)
        hist_mass_proj.SetBinError(i+1, mean_sp_err)

    if debug:
        hist_vn_proj.Write()
        hist_mass_proj.Write()
        outfile.Close()

    return hist_mass_proj


def get_resolution(dets, det_lables, cent_min_max):
    '''
    Compute resolution for SP or EP method

    Input:
        - dets:
            list of TH2D, list of TH2D objects with the SP product or EP cos(deltaphi) values vs centrality
        - det_lables:
            list of strings, list of detector labels
        - cent_min_max:
            list of floats, max and min centrality bins

    Output:
        - histo_means:
            list of TH1D, list of histograms with the mean value of the projections as a function of centrality for 1% bins
        - histo_means_deltacent:
            list of TH1D, list of histograms with the mean value of the projections as a function of centrality for CentMin-CentMax
        - histo_reso:
            TH1D, histogram with the resolution value as a function of centrality for 1% bins
        - histo_reso_delta_cent:
            TH1D, histogram with the resolution value as a function of centrality for CentMin-CentMax
    '''
    histo_projs, histo_means, histo_means_deltacent = [], [], []

    # collect the qvecs and prepare histo for mean and resolution
    for _, (det, det_label) in enumerate(zip(dets, det_lables)):
        print(f'Processing {det_label}')
        # th1 for mean 1% centrality bins
        histo_means.append(ROOT.TH1F('', '', cent_min_max[1]-cent_min_max[0], cent_min_max[0], cent_min_max[1]))
        histo_means[-1].SetDirectory(0)
        histo_means[-1].SetName(f'proj_{det_label}_mean')
        # th1 for mean CentMin-CentMax
        histo_projs.append([])
        hist_proj_dummy = det.ProjectionY(f'proj_{det.GetName()}_mean_deltacent',
                                          det.GetXaxis().FindBin(cent_min_max[0]),
                                          det.GetXaxis().FindBin(cent_min_max[1])-1)
        histo_means_deltacent.append(ROOT.TH1F('', '', 1, cent_min_max[0], cent_min_max[1]))
        histo_means_deltacent[-1].SetDirectory(0)
        histo_means_deltacent[-1].SetName(f'proj_{det_label}_mean_deltacent')

        # Set mean values for CentMin-CentMax
        histo_means_deltacent[-1].SetBinContent(1, hist_proj_dummy.GetMean())
        histo_means_deltacent[-1].SetBinError(1, hist_proj_dummy.GetMeanError())
        del hist_proj_dummy

        # collect projections 1% centrality bins
        for cent in range(cent_min_max[0], cent_min_max[1]):
            bin_cent = det.GetXaxis().FindBin(cent) # common binning
            histo_projs[-1].append(det.ProjectionY(f'proj_{det_label}_{cent}',
                                                          bin_cent, bin_cent))
        # Set mean values for 1% centrality bins
        for ihist, _ in enumerate(histo_projs[-1]):
            histo_means[-1].SetBinContent(ihist+1, histo_projs[-1][ihist].GetMean())

    # Compute resolution for 1% centrality bins
    histo_reso = ROOT.TH1F('histo_reso', 'histo_reso',
                           cent_min_max[1]-cent_min_max[0],
                           cent_min_max[0], cent_min_max[1])
    histo_reso.SetDirectory(0)
    for icent in range(cent_min_max[0], cent_min_max[1]):
        reso = compute_resolution([histo_means[i].GetBinContent(icent-cent_min_max[0]+1) for i in range(len(dets))])
        centbin = histo_reso.GetXaxis().FindBin(icent)
        histo_reso.SetBinContent(centbin, reso)

    # Compute resolution for CentMin-CentMax
    histo_reso_delta_cent = ROOT.TH1F('histo_reso_delta_cent', 'histo_reso_delta_cent',
                                      1, cent_min_max[0], cent_min_max[1])
    res_deltacent = compute_resolution([histo_means_deltacent[i].GetBinContent(1) for i in range(len(dets))])
    histo_reso_delta_cent.SetBinContent(1, res_deltacent)
    histo_reso_delta_cent.SetDirectory(0)

    return histo_means, histo_means_deltacent, histo_reso, histo_reso_delta_cent

def getListOfHisots(an_res_file, wagon_id, vn_method):
    '''
    Get list of histograms for SP or EP resolution

    Input:
        - an_res_file:
            str, resolution file
        - wagon_id:
            str, wagon ID
        - vn_method:
            str, vn method (sp or ep)

    Output:
        - correct_histo_triplets:
            list of TH2D, list of TH2D objects with the SP product or EP cos(deltaphi) values vs centrality
        - correct_histo_labels:
            list of strings, list of detector labels
    '''
    infile_path = f'hf-task-flow-charm-hadrons'
    if wagon_id:
        infile_path = f'{infile_path}_id{wagon_id}'
    if vn_method != 'sp':
        infile_path = f'{infile_path}/{vn_method}Reso'
        prefix = f'hEpReso'
    else:
        infile_path = f'{infile_path}/spReso'
        prefix = 'hSpReso'

    infile = ROOT.TFile(an_res_file, 'READ')
    directory = infile.GetDirectory(infile_path)
    histos = [key.ReadObj() for key in directory.GetListOfKeys()]
    for histo in histos:
        histo.SetDirectory(0)
    pairs = [key.GetName() for key in directory.GetListOfKeys()]

    # generate triplets of pairs (AB, AC, BC)
    triplets = []
    detsA = ['FT0c', 'FT0a', 'FV0a', 'TPCpos', 'FT0m', 'TPCneg']
    triplets = list(combinations(pairs, 3))
    histo_triplets = list(combinations(histos, 3))
    correct_histo_triplets = []
    correct_histo_labels = []
    for i, triplet in enumerate(triplets):
        for detA in detsA:
            detB = triplet[0].replace(prefix, '').replace(detA, '')
            detC = triplet[1].replace(prefix, '').replace(detA, '')
            if (detA in triplet[0] and detA in triplet[1]) and \
               (detB in triplet[0] and detB in triplet[2]) and \
               (detC in triplet[1] and detC in triplet[2]):
                correct_histo_triplets.append(histo_triplets[i])
                correct_histo_labels.append((detA, detB, detC))

    return correct_histo_triplets, correct_histo_labels

def compute_resolution(subMean):
    '''
    Compute resolution for SP or EP method

    Input:
        - subMean:
            list of floats, list of mean values of the projections

    Output:
        - resolution:
            float, resolution value
    '''
    print(subMean)
    if len(subMean) == 1:
        resolution =  subMean[0]
        if resolution <= 0:
            return 0
        else:
            return np.sqrt(resolution)
    elif len(subMean) == 3:
        print('3 subsystems')
        resolution = (subMean[0] * subMean[1]) / subMean[2] if subMean[2] != 0 else 0
        if resolution <= 0:
            return 0
        else:
            print(resolution, np.sqrt(resolution))
            return np.sqrt(resolution)
    else:
        print('ERROR: dets must be a list of 2 or 3 subsystems')
        sys.exit(1)

def get_centrality_bins(centrality):
    '''
    Get centrality bins

    Input:
        - centrality:
            str, centrality class (e.g. 'k3050')

    Output:
        - cent_bins:
            list of floats, centrality bins
        - cent_label:
            str, centrality label
    '''
    if centrality == 'k010':
        return '0_10', [0, 10]
    if centrality == 'k020':
        return '0_20', [0, 20]
    if centrality == 'k2030':
        return '20_30', [20, 30]
    elif centrality == 'k3040':
        return '30_40', [30, 40]
    elif centrality == 'k3050':
        return '30_50', [30, 50]
    elif centrality == 'k4050':
        return '40_50', [40, 50]
    elif centrality == 'k2060':
        return '20_60', [20, 60]
    elif centrality == 'k4060':
        return '40_60', [40, 60]
    elif centrality == 'k6070':
        return '60_70', [60, 70]
    elif centrality == 'k6080':
        return '60_80', [60, 80]
    elif centrality == 'k7080':
        return '70_80', [70, 80]
    elif centrality == 'k0100':
        return '0_100', [0, 100]
    else:
        print(f"ERROR: cent class \'{centrality}\' is not supported! Exit")
    sys.exit()

def compute_r2(reso_file, wagon_id, cent_min, cent_max, detA, detB, detC, vn_method):
    '''
    Compute resolution for SP or EP method
    
    Input:
        - reso_file:
            TFile, resolution file
        - wagon_id:
            str, wagon ID
        - cent_min:
            int, minimum centrality bin
        - cent_max:
            int, maximum centrality bin
        - detA:
            str, detector A
        - detB:
            str, detector B
        - detC:
            str, detector C
        - do_ep:
            bool, if True, compute EP resolution
            if False, compute SP resolution

    Output:
        - reso:
            float, resolution value
    '''
    if wagon_id != '':
        wagon_id = f'{wagon_id}'
    if vn_method != 'sp':
        hist_name = f'hf-task-flow-charm-hadrons{wagon_id}/epReso/hEpReso'
    else:
        hist_name = f'hf-task-flow-charm-hadrons{wagon_id}/spReso/hSpReso'

    detA_detB = reso_file.Get(f'{hist_name}{detA}{detB}')
    detA_detC = reso_file.Get(f'{hist_name}{detA}{detC}')
    detB_detC = reso_file.Get(f'{hist_name}{detB}{detC}')

    cent_bin_min = detA_detB.GetXaxis().FindBin(cent_min)
    cent_bin_max = detA_detB.GetXaxis().FindBin(cent_max)

    proj_detA_detB = detA_detB.ProjectionY(f'{hist_name}{detA}{detB}_proj{cent_min}_{cent_max}',
                                           cent_bin_min, cent_bin_max)
    proj_detA_detC = detA_detC.ProjectionY(f'{hist_name}{detA}{detC}_proj{cent_min}_{cent_max}',
                                           cent_bin_min, cent_bin_max)
    proj_detB_detC = detB_detC.ProjectionY(f'{hist_name}{detB}{detC}_proj{cent_min}_{cent_max}',
                                           cent_bin_min, cent_bin_max)

    average_detA_detB = proj_detA_detB.GetMean()
    average_detA_detC = proj_detA_detC.GetMean()
    average_detB_detC = proj_detB_detC.GetMean()

    reso = (average_detA_detB * average_detA_detC) / average_detB_detC if average_detB_detC != 0 else -999
    reso = np.sqrt(reso) if reso > 0 else -999
    return reso

# TODO: extend to vn not only v2
def get_invmass_vs_deltaphi(thnSparse, deltaphiaxis, invmassaxis):
    '''
    Project invariant mass versus deltaphi
    
    Input:
        - thnSparse:
            THnSparse, input THnSparse obeject
        - deltaphiaxis:
            int, axis number for deltaphi
        - invmassaxis:
            int, axis number for invariant mass

    Output:
        - hist_invMass_in:
            TH1D, histogram with invariant mass for in-plane
        - hist_invMass_out:
            TH1D, histogram with invariant mass for out-of-plane
    ''' 
    thn_inplane = thnSparse.Clone('thn_inplane')
    thn_outplane = thnSparse.Clone('thn_outplane')
    hist_cosDeltaPhi_inplane = thn_inplane.Projection(deltaphiaxis, invmassaxis)
    hist_cosDeltaPhi_outplane = thn_outplane.Projection(deltaphiaxis, invmassaxis)
    # In-plane (|cos(deltaphi)| < pi/4)
    hist_cosDeltaPhi_inplane.GetYaxis().SetRangeUser(0, 1)
    hist_invMass_in = hist_cosDeltaPhi_inplane.ProjectionX()
    # Out-of-plane (|cos(deltaphi)| > pi/4)
    hist_cosDeltaPhi_outplane.GetYaxis().SetRangeUser(-1, 0)
    hist_invMass_out = hist_cosDeltaPhi_outplane.ProjectionX()
    hist_invMass_in.SetLineColor(ROOT.kRed)
    del thn_inplane, thn_outplane, hist_cosDeltaPhi_inplane, hist_cosDeltaPhi_outplane
    
    return hist_invMass_in, hist_invMass_out

def get_vnfitter_results(vnFitter, secPeak):
    '''
    Get vn fitter results:
    0: BkgInt
    1: BkgSlope
    2: SgnInt
    3: Mean
    4: Sigma
    5: SecPeakInt
    6: SecPeakMean
    7: SecPeakSigma
    8: ConstVnBkg
    9: SlopeVnBkg
    10: v2Sgn
    11: v2SecPeak

    Input:
        - vnfitter:
            VnVsMassFitter, vn fitter object
        - secPeak:
            bool, if True, save secondary peak results

    Output:
        - vn_results:
            dict, dictionary with vn results
            vn: vn value
            vnUnc: uncertainty of vn value
            mean: mean value
            meanUnc: uncertainty of mean value
            sigma: sigma value
            sigmaUnc: uncertainty of sigma value
            ry: raw yield
            ryUnc: uncertainty of raw yield
            chi2: reduced chi2
            prob: fit probability
            fTotFuncMass: total fit function for mass
            fTotFuncVn: total fit function for vn
            secPeakMeanMass: secondary peak mean mass
            secPeakMeanMassUnc: uncertainty of secondary peak mean mass
            secPeakSigmaMass: secondary peak sigma mass
            secPeakSigmaMassUnc: uncertainty of secondary peak sigma mass
            secPeakMeanVn: secondary peak mean vn
            secPeakMeanVnUnc: uncertainty of secondary peak mean vn
            secPeakSigmaVn: secondary peak sigma vn
            secPeakSigmaVnUnc: uncertainty of secondary peak sigma vn
            vnSecPeak: vn secondary peak
            vnSecPeakUnc: uncertainty of vn secondary peak
    '''
    vn_results = {}
    vn_results['vn'] = vnFitter.GetVn()
    vn_results['vnUnc'] = vnFitter.GetVnUncertainty()
    vn_results['mean'] = vnFitter.GetMean()
    vn_results['meanUnc'] = vnFitter.GetMeanUncertainty()
    vn_results['sigma'] = vnFitter.GetSigma()
    vn_results['sigmaUnc'] = vnFitter.GetSigmaUncertainty()
    vn_results['ry'] = vnFitter.GetRawYield()
    vn_results['ryUnc'] = vnFitter.GetRawYieldUncertainty()
    vn_results['chi2'] = vnFitter.GetReducedChiSquare()
    vn_results['prob'] = vnFitter.GetFitProbability()
    vn_results['fTotFuncMass'] = vnFitter.GetMassTotFitFunc()
    vn_results['fTotFuncVn'] = vnFitter.GetVnVsMassTotFitFunc()
    vn_results['fBkgFuncMass'] = vnFitter.GetMassBkgFitFunc()
    vn_results['fBkgFuncVn'] = vnFitter.GetVnVsMassBkgFitFunc()
    vn_results['fSgnFuncMass'] = vnFitter.GetMassSignalFitFunc()
    bkg, bkgUnc = ctypes.c_double(), ctypes.c_double()
    vnFitter.Background(3, bkg, bkgUnc)
    vn_results['bkg'] = bkg.value
    vn_results['bkgUnc'] = bkgUnc.value
    sgn, sgnUnc = ctypes.c_double(), ctypes.c_double()
    vnFitter.Significance(3, sgn, sgnUnc)
    vn_results['sgn'] = sgn.value
    vn_results['sgnUnc'] = sgnUnc.value

    if secPeak:
        vn_results['secPeakMeanMass'] = vn_results['fTotFuncMass'].GetParameter(vn_results['fTotFuncMass'].GetParName(6))
        vn_results['secPeakMeanMassUnc'] = vn_results['fTotFuncMass'].GetParError(6)
        vn_results['secPeakSigmaMass'] = vn_results['fTotFuncMass'].GetParameter(vn_results['fTotFuncMass'].GetParName(7))
        vn_results['secPeakSigmaMassUnc'] = vn_results['fTotFuncMass'].GetParError(7)
        vn_results['secPeakMeanVn'] = vn_results['fTotFuncVn'].GetParameter(vn_results['fTotFuncVn'].GetParName(6))
        vn_results['secPeakMeanVnUnc'] = vn_results['fTotFuncVn'].GetParError(6)
        vn_results['secPeakSigmaVn'] = vn_results['fTotFuncVn'].GetParameter(vn_results['fTotFuncVn'].GetParName(7))
        vn_results['secPeakSigmaVnUnc'] = vn_results['fTotFuncVn'].GetParError(7)
        vn_results['vnSecPeak'] = vn_results['fTotFuncVn'].GetParameter(vn_results['fTotFuncVn'].GetParName(11))
        vn_results['vnSecPeakUnc'] = vn_results['fTotFuncVn'].GetParError(11)

    return vn_results

def get_ep_vn(harmonic, nIn, nInUnc, nOut, nOutUnc, resol=1, corr=0):
    '''
    Compute EP vn

    Input:
        - harmonic:
            int, harmonic number
        - nIn:
            float, number of in-plane particles
        - nInUnc:
            float, uncertainty of the number of in-plane particles
        - nOut:
            float, number of out-of-plane particles
        - nOutUnc:
            float, uncertainty of the number of out-of-plane particles
        - resol:
            float, resolution value (default: 1)
        - corr:
            float, correlation between nIn and nOut (default: 1)

    Output:
        - vn:
            float, vn value
        - vnunc:
            float, uncertainty of vn value
    '''
    print(corr)
    if nIn + nOut == 0:
        print('\033[91m ERROR: nIn + nOut = 0. Return 0, 0 \033[0m')
        return 0, 0
    anis = (nIn - nOut) / (nIn + nOut)
    anisDerivIn  = 2 * nOut / ((nIn + nOut)*(nIn + nOut))
    anisDerivOut = -2 * nIn / ((nIn + nOut)*(nIn + nOut))
    anisunc = anisDerivIn * anisDerivIn * nInUnc * nInUnc +\
              anisDerivOut * anisDerivOut * nOutUnc * nOutUnc + \
              2 * anisDerivIn * anisDerivOut * nInUnc * nOutUnc * corr
    if anisunc < 0:
        print('\033[91m ERROR: anisunc < 0. Return 0, 0 \033[0m')
        return 0, 0
    anisunc = np.sqrt(anisunc)

    vn = (np.pi * anis) / (harmonic * harmonic * resol)
    vnunc = (np.pi * anisunc) / (harmonic * harmonic * resol)

    return vn, vnunc

def check_file_exists(file_path):
    '''
    Check if file exists

    Input:
        - file_path:
            str, file path

    Output:
        - file_exists:
            bool, if True, file exists
    '''
    file_exists = False
    if os.path.exists(file_path):
        file_exists = True
    return file_exists

def check_histo_exists(file, histo_name):
    '''
    Check if histogram exists in file

    Input:
        - file:
            TFile, ROOT file
        - histo_name:
            str, histogram name

    Output:
        - histo_exists:
            bool, if True, histogram exists
    '''
    if not check_file_exists(file):
        return False
    file = ROOT.TFile(file, 'READ')
    histo_exists = False
    if file.Get(histo_name):
        histo_exists = True
    return histo_exists

def getD0ReflHistos(reflFile, ptMins, ptMaxs):
    '''
    Method that loads MC histograms for the reflections of D0

    Input:
        - reflFile:
           TFile, ROOT file, include reflections of D0 TODO: add which .py can produce reflection
        - ptMins:
            list, min pt bins
        - ptMaxs:
            list, max pt bins
    
    Output:
        - useRefl:
            bool, if True, MC histograms for the reflections of D0 exists
        - hMCSgn:
            lsit, signal histograms of D0
        - hMCRefl:
            list, reflection histograms of D0
    '''
    hMCSgn, hMCRefl = [], []
    if not check_file_exists(reflFile):
        print(f'Error: reflection file {reflFile} does not exist! Turning off reflections usage')
        return False
    
    reflFile = ROOT.TFile(reflFile, 'READ')

    for iPt, (ptMin, ptMax) in enumerate(zip(ptMins, ptMaxs)):

        hMCSgn.append(reflFile.Get(f'hFDMass_{ptMin}0_{ptMax}0'))
        print(f'hFDMass_{ptMin}_{ptMax}')
        hMCSgn[iPt].Add(reflFile.Get(f'hPromptMass_{ptMin}0_{ptMax}0'))
        if hMCSgn[iPt] == None:
            print(f'hFDMass_{ptMin}0_{ptMax}0 or hPromptMass_{ptMin}0_{ptMax}0 not found! Turning off reflections usage')
            return False
        hMCSgn[iPt].SetName(f'histSgn_{iPt}')
        hMCSgn[iPt].SetDirectory(0)

        hMCRefl.append(reflFile.Get(f'hVarReflMass_{ptMin}0_{ptMax}0'))
        if hMCRefl[iPt] == None:
            print(f'hVarReflMass_{ptMin}0_{ptMax}0 not found! Turning off reflections usage')
            return False
        hMCRefl[iPt].SetName(f'histRfl_{iPt},iPt')
        hMCRefl[iPt].SetDirectory(0)

    reflFile.Close()

    return True, hMCSgn, hMCRefl